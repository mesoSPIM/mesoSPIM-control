"""Fixes for errors seen on the bench when an acquisition was stopped (2026-11-12) and for
stage-limit refusals that were logged without details (2026-11-11).

- OME-Zarr MP writer: finalize() must not close the parent's shared-memory handle before the
  spawned writer process has attached, or the block is deleted on Windows and the child dies
  with FileNotFoundError (a stopped or very short stack).
- ImageWriter.end_acquisition: no max projection when no frames were written.
- mesoSPIM_Serial.stage_limits_OK: a refused move is logged as a WARNING with axis details.

Run: python -m pytest mesoSPIM/test/test_stop_writer_fixes.py
"""
import logging
import multiprocessing as mp
import os
import time
from multiprocessing import shared_memory
from types import SimpleNamespace

import pytest


def _attach_child(shm_name, attached, start_delay):
    """Spawned child: start slowly (like importing zarr), then attach and read the block."""
    time.sleep(start_delay)
    shm = shared_memory.SharedMemory(name=shm_name)
    attached.set()
    value = shm.buf[0]
    shm.close()
    if value != 42:
        raise SystemExit(2)


def _wait_for_writer_attach():
    from mesoSPIM.src.plugins.ImageWriters.OmeZarrWriterMP import wait_for_writer_attach
    return wait_for_writer_attach


def test_finalize_waits_for_a_slow_writer_to_attach():
    wait_for_writer_attach = _wait_for_writer_attach()
    ctx = mp.get_context('spawn')
    shm = shared_memory.SharedMemory(create=True, size=16)
    try:
        shm.buf[0] = 42
        attached = ctx.Event()
        proc = ctx.Process(target=_attach_child, args=(shm.name, attached, 1.0), daemon=True)
        proc.start()
        assert wait_for_writer_attach(proc, attached, timeout=60)
        shm.close()  # what finalize() does next
        proc.join(30)
        assert proc.exitcode == 0
    finally:
        shm.close()
        shm.unlink()


def test_wait_returns_false_when_the_writer_dies_before_attaching():
    wait_for_writer_attach = _wait_for_writer_attach()
    ctx = mp.get_context('spawn')
    attached = ctx.Event()
    proc = ctx.Process(target=_attach_child, args=('no_such_shm_block_mesospim', attached, 0.0), daemon=True)
    proc.start()
    t0 = time.monotonic()
    assert not wait_for_writer_attach(proc, attached, timeout=60)
    assert time.monotonic() - t0 < 30  # returned because the process died, not on the timeout
    proc.join(10)


def test_wait_times_out():
    wait_for_writer_attach = _wait_for_writer_attach()
    alive = SimpleNamespace(is_alive=lambda: True)
    event = mp.get_context('spawn').Event()
    assert not wait_for_writer_attach(alive, event, timeout=0.2, poll=0.05)
    event.set()
    assert wait_for_writer_attach(alive, event, timeout=0.2)


def test_end_acquisition_without_frames_skips_the_max_projection(tmp_path, caplog):
    from mesoSPIM.src.mesoSPIM_ImageWriter import mesoSPIM_ImageWriter
    mip_path = tmp_path / 'MAX_empty.tiff'
    import tifffile
    finalized, done = [], []
    fake = SimpleNamespace(
        running_flag=True, frame_queue=[], cur_image_counter=0, max_frame=401, path='x.ome.zarr',
        writer=SimpleNamespace(finalize=finalized.append),
        mip_image=None, MIP_path=str(mip_path),
        tiff_mip_writer=tifffile.TiffWriter(str(mip_path), imagej=True),
        sig_end_acquisition_done=SimpleNamespace(emit=lambda: done.append(True)),
    )
    with caplog.at_level(logging.WARNING):
        mesoSPIM_ImageWriter.end_acquisition(fake, {'processing': 'MAX'}, ['acq'])
    assert finalized and done and fake.running_flag is False
    assert not mip_path.exists()
    assert "no attribute 'T'" not in caplog.text
    assert 'No max projection saved' in caplog.text


# Stage-limit refusals: see test_stage_limits.py (soft-limit guard for every stage type).
