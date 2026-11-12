"""Channel settings files: per (laser, zoom) ETL parameters and absolute focus (F) positions.

A channel settings file is the former "ETL config file", a semicolon-separated CSV with one row per
laser line (``Wavelength``) and magnification (``Zoom``)::

    Objective;Wavelength;Zoom;ETL-Left-Offset;ETL-Left-Amp;ETL-Right-Offset;ETL-Right-Amp;F-Absolute-um
    1x;488 nm;2x;2.31;0.70;2.36;0.65;5012.5

``F-Absolute-um`` is the focus stage position in **physical stage coordinates** (micrometres, not shifted
by the user's F zeroing), so it stays valid after the F axis is zeroed. The column is optional: ETL files
written before it existed still load, and an empty cell means "no F position stored for this channel".

Nothing in this module moves hardware. :func:`evaluate_f_target` only decides whether a stored F position
may be *offered* to the user; the move itself needs the user's explicit approval (see mesoSPIM_Core).
"""
import csv
import math
import os

import logging
logger = logging.getLogger(__name__)

F_COLUMN = 'F-Absolute-um'
ETL_COLUMNS = ('ETL-Left-Offset', 'ETL-Left-Amp', 'ETL-Right-Offset', 'ETL-Right-Amp')
FIELDNAMES = ('Objective', 'Wavelength', 'Zoom') + ETL_COLUMNS + (F_COLUMN,)

MAX_F_JUMP_UM = 500.0   # a stored F further than this from the current F is flagged and never moved to
F_TOLERANCE_UM = 0.5    # closer than this: already in focus, nothing to offer

# evaluate_f_target() outcomes
F_DISABLED = 'disabled'       # F loading is switched off: F values in the file are ignored
F_MISSING = 'missing'         # no (valid) F stored for this channel: flag, no motion
F_TOO_FAR = 'too_far'         # more than MAX_F_JUMP_UM away from the current F: flag, no motion
F_OUT_OF_LIMITS = 'out_of_limits'  # outside the configured f_min/f_max: flag, no motion
F_IN_PLACE = 'in_place'       # already there: nothing to do
F_OFFER = 'offer'             # may be offered to the user for explicit approval


def clean_zoom(zoom):
    """``'2x Mitutoyo'`` -> ``'2x'``, the form ETL files have always used in the ``Zoom`` column."""
    return str(zoom).split('x')[0] + 'x'


def parse_f(value):
    """The F cell of a row as float, or None if empty, missing or not a finite number."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        f = float(text)
    except ValueError:
        logger.warning(f'Channel settings: F position {text!r} is not a number, ignored')
        return None
    return f if math.isfinite(f) else None


def _row_matches(row, laser, zoom):
    return row.get('Wavelength') == laser and row.get('Zoom') in (clean_zoom(zoom), zoom)


def read_channel_settings(path, laser, zoom):
    """Settings stored for (laser, zoom), or None if the file has no such row.

    Returns a dict with the ETL state keys ``etl_l_offset``, ``etl_l_amplitude``, ``etl_r_offset``,
    ``etl_r_amplitude`` and ``f_abs`` (float, or None when the file has no F for this channel, e.g. an
    old ETL-only file). The last matching row wins, as it always did.
    """
    result = None
    with open(path, newline='') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            if _row_matches(row, laser, zoom):
                result = {'etl_l_offset': float(row['ETL-Left-Offset']),
                          'etl_l_amplitude': float(row['ETL-Left-Amp']),
                          'etl_r_offset': float(row['ETL-Right-Offset']),
                          'etl_r_amplitude': float(row['ETL-Right-Amp']),
                          'f_abs': parse_f(row.get(F_COLUMN)),
                          }
    return result


def write_channel_settings(path, laser, zoom, etl_params, f_abs):
    """Store the settings of (laser, zoom) in the file: update its row, or append one.

    ``etl_params`` holds the ``etl_*`` state keys; ``f_abs`` is the physical F position (None leaves the
    cell empty). Other rows are copied unchanged; rows of old ETL-only files get an empty F cell. Unknown
    extra columns are kept. The file is replaced only after the new one was written completely.
    """
    tmp_path = path + '_tmp'
    with open(path, newline='') as input_file:
        reader = csv.DictReader(input_file, delimiter=';')
        rows = list(reader)
        extra = [name for name in (reader.fieldnames or []) if name not in FIELDNAMES]
    new_row = {'Objective': '1x',
               'Wavelength': laser,
               'Zoom': zoom,
               'ETL-Left-Offset': etl_params['etl_l_offset'],
               'ETL-Left-Amp': etl_params['etl_l_amplitude'],
               'ETL-Right-Offset': etl_params['etl_r_offset'],
               'ETL-Right-Amp': etl_params['etl_r_amplitude'],
               F_COLUMN: '' if f_abs is None else round(float(f_abs), 2),
               }
    with open(tmp_path, 'w', newline='') as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(FIELDNAMES) + extra, dialect='excel',
                                delimiter=';', restval='', extrasaction='ignore')
        writer.writeheader()
        match_found = False
        for row in rows:
            # exact zoom match, as before: a '2x' row is not overwritten by a '2x Mitutoyo' save
            if row.get('Wavelength') == laser and row.get('Zoom') == zoom:
                writer.writerow({**{k: v for k, v in row.items() if k in extra}, **new_row})
                match_found = True
            else:
                writer.writerow(row)
        if not match_found:
            writer.writerow(new_row)
    os.replace(tmp_path, path)
    return match_found


def channel_f_offer_key(offer):
    """Identity of an F offer for de-duplication: same channel, file, stored F and current F (0.1 um)."""
    return (offer['laser'], offer['zoom'], offer['file'], offer['f_abs'], round(offer['f_current'], 1))


def evaluate_f_target(f_target, f_current, enabled, f_limits=None, max_jump=MAX_F_JUMP_UM):
    """Decide what to do with an F position from a channel settings file. Never moves anything.

    Args:
        f_target: stored physical F (um), or None if the file has none for this channel.
        f_current: current physical F (um).
        enabled: whether loading F positions from channel files is switched on.
        f_limits: optional (f_min, f_max) of the stage, physical coordinates.
        max_jump: largest |f_target - f_current| that may be offered (um).

    Returns:
        (outcome, message): outcome is one of the F_* constants; message is for the log/GUI (empty for
        F_DISABLED and F_IN_PLACE). Only F_OFFER may lead to a move, and only after explicit approval.
    """
    if not enabled:
        return F_DISABLED, ''
    if f_target is None:
        return F_MISSING, ('No F position stored for this channel in the channel settings file. '
                           'F was not moved.')
    delta = f_target - f_current
    if f_limits is not None:
        f_min, f_max = f_limits
        if not (f_min < f_target < f_max):
            return F_OUT_OF_LIMITS, (f'Stored F position {f_target:.1f} um is outside the stage limits '
                                     f'({f_min}, {f_max}). F was not moved.')
    if abs(delta) > max_jump:
        return F_TOO_FAR, (f'Stored F position {f_target:.1f} um is {delta:+.1f} um away from the current F '
                           f'({f_current:.1f} um), more than {max_jump:.0f} um. F was not moved: '
                           f'check the channel settings file and move F manually if it is correct.')
    if abs(delta) < F_TOLERANCE_UM:
        return F_IN_PLACE, ''
    return F_OFFER, (f'Move F from {f_current:.1f} um to the stored {f_target:.1f} um ({delta:+.1f} um)?')
