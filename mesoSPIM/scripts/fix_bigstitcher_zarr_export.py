#!/usr/bin/env python3
"""
fix_bigstitcher_zarr_scale.py

Transfer voxel-scale metadata from a BigStitcher XML (or mesoSPIM acquisition
directory) into a BigStitcher-produced OME-Zarr, which otherwise lacks
coordinate scale information.

Usage examples
--------------
# Single pair
python fix_bigstitcher_zarr_scale.py dataset.ome.zarr.xml fused.ome.zarr

# Multiple pairs
python fix_bigstitcher_zarr_scale.py \\
    sample1.ome.zarr.xml fused1.ome.zarr \\
    sample2.ome.zarr.xml fused2.ome.zarr

# Dry-run (prints what would be written, does not modify files)
python fix_bigstitcher_zarr_scale.py dataset.ome.zarr.xml fused.ome.zarr --dry-run
"""

import json
from pathlib import Path
from typing import Any, List
from xml.etree import ElementTree as ET

import typer

# ---------------------------------------------------------------------------
# Inlined helpers (sourced from mesospim_utils)
# ---------------------------------------------------------------------------

def ensure_path(file_name: Path) -> Path:
    """Returns a Path object of the input file_name."""
    if not isinstance(file_name, Path):
        return Path(file_name)
    return file_name


def get_channel_names_from_xml(xml_path: Path) -> list[str]:
    """
    Parse channel names from a BigStitcher XML file.

    Channel names are stored under:
      SequenceDescription/ViewSetups/Attributes[@name='channel']/Channel/name
    e.g. "488 nm", "561 nm"

    Returns a list of name strings in channel-index order.
    """
    xml_path = ensure_path(xml_path)
    tree = ET.parse(xml_path)
    root = tree.getroot()

    channels = {}
    for attrs in root.iter("Attributes"):
        if attrs.get("name") == "channel":
            for ch in attrs.iter("Channel"):
                ch_id = int(ch.findtext("id", default="0"))
                ch_name = ch.findtext("name", default=f"channel_{ch_id}")
                channels[ch_id] = ch_name

    if not channels:
        return []

    # Return sorted by channel id
    return [channels[k] for k in sorted(channels.keys())]


def does_dir_contain_bigstitcher_metadata(path) -> Path | None:
    """
    Check if directory contains a BigStitcher XML file.
    Tries *.ome.zarr.xml first, then falls back to any *.xml.
    Returns None if not found, else the path to the xml file.
    """
    path = ensure_path(path)
    # Preferred: explicit ome.zarr.xml
    zarr_xml_files = list(path.glob("*.ome.zarr.xml"))
    if zarr_xml_files:
        return zarr_xml_files[0]
    # Fallback: any xml (e.g. dataset.xml produced by BigStitcher)
    xml_files = list(path.glob("*.xml"))
    xml_files = [f for f in xml_files if not f.name.endswith(".xml~1")]  # skip backups
    if xml_files:
        return xml_files[0]
    return None


def _list_mesospim_ome_zarr_tile_dirs(path_to_mesospim_omezarr: Path) -> list:
    path_to_mesospim_omezarr = ensure_path(path_to_mesospim_omezarr)
    tile_dir_list = path_to_mesospim_omezarr.glob("*")
    return [p for p in tile_dir_list if p.is_dir()]


def _list_mesospim_ome_zarr_zattrs(path_to_mesospim_omezarr: Path) -> list:
    tile_dir_list = _list_mesospim_ome_zarr_tile_dirs(path_to_mesospim_omezarr)
    zattrs_list = [x / ".zattrs" for x in tile_dir_list]
    return [x for x in zattrs_list if x.is_file()]


def determine_sampling_factors_for_bigstitcher(omezarr_xml_path: Path) -> tuple[list[Any], list, str]:
    """
    Determine subsampling factors string for BigStitcher from ome-zarr zattrs.
    Returns (scales_list, scale_factors_list, subsampling_factors_str).

    The XML can be either:
      - dataset.ome.zarr.xml  → sibling directory is dataset.ome.zarr/
      - dataset.xml           → looks for a *.ome.zarr or *.zarr sibling directory
    """
    omezarr_xml_path = ensure_path(omezarr_xml_path)
    parent = omezarr_xml_path.parent

    # Case 1: classic ome.zarr.xml — strip .xml to get the zarr dir
    if omezarr_xml_path.name.endswith(".ome.zarr.xml"):
        zarr_dir = str(omezarr_xml_path).removesuffix(".xml")
    else:
        # Case 2: plain dataset.xml — find the .ome.zarr or .zarr sibling
        candidates = list(parent.glob("*.ome.zarr")) + list(parent.glob("*.zarr"))
        candidates = [c for c in candidates if c.is_dir()]
        if not candidates:
            raise FileNotFoundError(
                f"Could not find a source .zarr directory alongside {omezarr_xml_path}. "
                f"Looked in: {parent}"
            )
        zarr_dir = str(candidates[0])
        typer.echo(f"  [info] Source zarr for scale reading: {zarr_dir}")

    zattrs_list = _list_mesospim_ome_zarr_zattrs(zarr_dir)
    if not zattrs_list:
        raise FileNotFoundError(
            f"No .zattrs found inside subdirectories of source zarr: {zarr_dir}"
        )
    zattr_file = zattrs_list[0]
    typer.echo(f"  [info] Reading scale from: {zattr_file}")
    zattr_data = json.loads(zattr_file.read_text())
    multiscales_dict = zattr_data.get("multiscales", [])[0]
    datasets_list = multiscales_dict.get("datasets", [])

    scales_list = []
    for scale in datasets_list:
        for coord_transform in scale.get("coordinateTransformations"):
            if coord_transform.get("type") == "scale":
                scales_list.append(coord_transform.get("scale"))

    scale_factors_list = []
    for idx, _ in enumerate(scales_list):
        if idx == 0:
            scale_factors_list.append([1, 1, 1])
        else:
            factors = [
                round(scales_list[idx][0] / scales_list[idx - 1][0]),
                round(scales_list[idx][1] / scales_list[idx - 1][1]),
                round(scales_list[idx][2] / scales_list[idx - 1][2]),
            ]
            scale_factors_list.append(factors)

    for idx, _ in enumerate(scale_factors_list):
        if idx == 0:
            scale_factors_list[idx] = scale_factors_list[0]
        else:
            scale_factors_list[idx] = [
                x * y for x, y in zip(scale_factors_list[idx - 1], scale_factors_list[idx])
            ]

    subsampling_factors_str = "{"
    for factors in scale_factors_list:
        subsampling_factors_str += "{" + f"{factors[2]},{factors[1]},{factors[0]}" + "},"
    subsampling_factors_str = subsampling_factors_str.rstrip(",") + "}"

    return scales_list, scale_factors_list, subsampling_factors_str


# ---------------------------------------------------------------------------
# Core fix logic
# ---------------------------------------------------------------------------

def _fix_one(
    omezarr_xml_or_acquisition_path: Path,
    omezarr_produced_by_bigstitcher_path: Path,
    dry_run: bool = False,
):
    omezarr_xml_or_acquisition_path = ensure_path(omezarr_xml_or_acquisition_path)
    omezarr_produced_by_bigstitcher_path = ensure_path(omezarr_produced_by_bigstitcher_path)

    if omezarr_xml_or_acquisition_path.as_posix().endswith(".ome.zarr.xml"):
        omezarr_xml = omezarr_xml_or_acquisition_path
    else:
        omezarr_xml = does_dir_contain_bigstitcher_metadata(omezarr_xml_or_acquisition_path)
        omezarr_xml = ensure_path(omezarr_xml)

    scales_list_zyx, _, _ = determine_sampling_factors_for_bigstitcher(omezarr_xml)
    typer.echo(f"  [info] Source has {len(scales_list_zyx)} resolution level(s):")
    for i, s in enumerate(scales_list_zyx):
        typer.echo(f"           level {i}: {s}")

    # Allow the user to pass either the .zarr directory directly, or a parent
    # directory that contains a single .zarr subdirectory (e.g. fused-LeftHalf/fused.zarr)
    zarr_root = ensure_path(omezarr_produced_by_bigstitcher_path)
    target_zattr_path = zarr_root / ".zattrs"
    if not target_zattr_path.exists():
        zarr_subdirs = list(zarr_root.glob("*.zarr"))
        if len(zarr_subdirs) == 1:
            zarr_root = zarr_subdirs[0]
            target_zattr_path = zarr_root / ".zattrs"
            typer.echo(f"  [info] Found zarr store at: {zarr_root}")
        elif len(zarr_subdirs) > 1:
            names = ", ".join(str(p.name) for p in zarr_subdirs)
            raise FileNotFoundError(
                f"Multiple .zarr directories found in {zarr_root}: {names}. "
                f"Please pass the exact .zarr path."
            )
        else:
            raise FileNotFoundError(
                f".zattrs not found at {target_zattr_path} and no .zarr "
                f"subdirectory found inside {zarr_root}."
            )

    target_zattr = json.loads(target_zattr_path.read_text())
    target_datasets = target_zattr.get("multiscales", [])[0].get("datasets", [])
    typer.echo(f"  [info] Target has {len(target_datasets)} resolution level(s):")

    # Base voxel size from source (s0), axes order is (t, c, z, y, x)
    source_z  = scales_list_zyx[0][0]   # e.g. 4.0 µm
    source_xy = scales_list_zyx[0][1]   # e.g. 0.17 µm

    for dataset in target_datasets:
        path = dataset.get("path")       # e.g. "0", "1", ... "7"
        coord_transform = dataset["coordinateTransformations"][0]

        # Read downsamplingFactors from the per-level .zattrs
        # BigStitcher writes them as [x_factor, y_factor, z_factor, 1, 1]
        level_zattrs_path = zarr_root / path / ".zattrs"
        if level_zattrs_path.exists():
            level_zattrs = json.loads(level_zattrs_path.read_text())
            factors = level_zattrs.get("downsamplingFactors", None)
        else:
            factors = None

        if factors is not None:
            # downsamplingFactors order from BigStitcher: [x, y, z, c, t]
            factor_x = factors[0]
            factor_y = factors[1]
            factor_z = factors[2]
            new_scale = [
                1.0,                        # t
                1.0,                        # c
                source_z  * factor_z,       # z
                source_xy * factor_y,       # y
                source_xy * factor_x,       # x
            ]
            typer.echo(
                f"    level {path}: downsamplingFactors={factors} "
                f"-> scale={new_scale}"
            )
        else:
            # Fallback: keep existing scale but fix Z proportionally
            current_scale = coord_transform["scale"]
            new_scale = list(current_scale)
            new_scale[2] = source_z
            typer.echo(
                f"    level {path}: no downsamplingFactors found, "
                f"using fallback scale={new_scale}"
            )

        coord_transform["scale"] = new_scale

    # --- Channel names + colors ---
    # napari-ome-zarr requires a 'color' (hex) on every omero.channels entry.
    # If it is missing, napari crashes with "colormap provided 0 values".
    DEFAULT_COLORS = [
        "00FF00",  # green
        "FF00FF",  # magenta
        "00FFFF",  # cyan
        "FF0000",  # red
        "0000FF",  # blue
        "FFFF00",  # yellow
    ]

    channel_names = get_channel_names_from_xml(omezarr_xml)
    if channel_names:
        typer.echo(f"  [info] Channel names from XML: {channel_names}")
    else:
        typer.echo("  [warn] No channel names found in XML — will still ensure colors are set.")

    # Determine number of channels from the data shape (axis 1 in t,c,z,y,x)
    omero = target_zattr.setdefault("omero", {})
    existing_channels = omero.get("channels", [])

    # Use the larger of: existing list, number of names found
    n_channels = max(len(existing_channels), len(channel_names) if channel_names else 0)

    # Fallback: infer from axes metadata if still 0
    if n_channels == 0:
        axes = target_zattr.get("multiscales", [{}])[0].get("axes", [])
        axis_names = [a.get("name", "") for a in axes]
        if "c" in axis_names:
            c_idx = axis_names.index("c")
            # We can't easily read array shape here, default to 2
            n_channels = 2
            typer.echo(f"  [warn] Could not determine channel count, defaulting to {n_channels}.")

    while len(existing_channels) < n_channels:
        existing_channels.append({})

    for i in range(n_channels):
        # Set label if available
        if channel_names and i < len(channel_names):
            existing_channels[i]["label"] = channel_names[i]
        # Always ensure color is present — do not overwrite if already set
        if "color" not in existing_channels[i]:
            existing_channels[i]["color"] = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]

    omero["channels"] = existing_channels
    typer.echo(f"  [info] omero.channels written: {existing_channels}")

    if dry_run:
        typer.echo(f"[dry-run] Would write the following to {target_zattr_path}:")
        typer.echo(json.dumps(target_zattr, indent=4))
    else:
        with open(target_zattr_path, "w") as f:
            json.dump(target_zattr, f, indent=4)
        typer.echo(f"[ok] Scale written to {target_zattr_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

app = typer.Typer(help=__doc__)


@app.command()
def fix_scale(
    xml_paths: List[Path] = typer.Option(
        ...,
        "--xml", "-x",
        help=(
            "Path to a BigStitcher .ome.zarr.xml file or a mesoSPIM acquisition "
            "directory. Repeat for multiple datasets."
        ),
    ),
    zarr_paths: List[Path] = typer.Option(
        ...,
        "--zarr", "-z",
        help=(
            "Path to the BigStitcher-produced OME-Zarr to fix. "
            "Must be provided once for every --xml, in the same order."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the modified .zattrs to stdout without writing to disk.",
    ),
):
    """Fix missing scale metadata in BigStitcher-produced OME-Zarr files."""

    if len(xml_paths) != len(zarr_paths):
        typer.echo(
            f"[error] Number of --xml arguments ({len(xml_paths)}) must match "
            f"number of --zarr arguments ({len(zarr_paths)}).",
            err=True,
        )
        raise typer.Exit(code=1)

    paired = list(zip(xml_paths, zarr_paths))
    errors = []

    for i, (xml, zarr) in enumerate(paired, start=1):
        typer.echo(f"\n[{i}/{len(paired)}] Processing:")
        typer.echo(f"  xml  : {xml}")
        typer.echo(f"  zarr : {zarr}")
        try:
            _fix_one(xml, zarr, dry_run=dry_run)
        except Exception as e:
            typer.echo(f"  [error] {e}", err=True)
            errors.append((xml, zarr, e))

    if errors:
        typer.echo(f"\n{len(errors)} pair(s) failed:", err=True)
        for xml, zarr, e in errors:
            typer.echo(f"  {xml} -> {zarr}: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo("\nDone.")


if __name__ == "__main__":
    app()