"""Shared mapping of capture outcomes to exit codes and French messages."""

import logging
import sys
from collections.abc import Callable

from opendofusdata.capture import CaptureAborted, PacketPipeline

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

CAPTURE_FAILED_MESSAGE = (
    "Capture impossible ({error}). Vérifiez Npcap, le nom de "
    "l'interface, et essayez un terminal administrateur."
)
CaptureFunction = Callable[[PacketPipeline, str | None], None]


def fail(message: str) -> int:
    """Print an error message on stderr and return the failure exit code."""
    print(message, file=sys.stderr)
    return EXIT_FAILED


def run_guarded_capture(
    capture: CaptureFunction,
    pipeline: PacketPipeline,
    interface: str | None,
    stop_message: Callable[[], str],
    abort_message: Callable[[CaptureAborted], str],
) -> int:
    """Run a capture and map Ctrl+C, aborts and failures to an exit code and message."""
    try:
        capture(pipeline, interface)
    except KeyboardInterrupt:
        print(stop_message())
        return EXIT_OK
    except CaptureAborted as error:
        return fail(abort_message(error))
    # scapy raises several unrelated types when Npcap or the interface is unusable.
    except Exception as error:
        logger.debug("capture failure", exc_info=True)
        return fail(CAPTURE_FAILED_MESSAGE.format(error=error))
    return EXIT_OK
