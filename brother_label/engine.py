import logging
import time

from brother_label.backends.base import Backend
from brother_label.reader import interpret_response

logger = logging.getLogger(__name__)


def communicate(instructions: bytes, backend: Backend, blocking: bool = True):
    """Send instruction bytes to a printer.

    :param bytes instructions: The instructions to be sent to the printer.
    :param bool blocking: Indicates whether the function call should block while waiting
        for the completion of the printing.
    """
    status = {
        # The instructions were sent to the printer.
        "instructions_sent": True,
        # String description of the outcome of the sending operation like:
        # 'unknown', 'sent', 'printed', 'error'
        "outcome": "unknown",
        # If the selected backend supports reading back the printer state, this key will
        # contain it.
        "printer_state": None,
        # If True, a print was produced. It defaults to False if the outcome is
        # uncertain (due to a backend without read-back capability).
        "did_print": False,
        # If True, the printer is ready to receive the next instructions. It defaults to
        # False if the state is unknown.
        "ready_for_next_job": False,
    }

    start = time.time()
    logger.info(
        "Sending instructions to the printer. Total: %d bytes.",
        len(instructions),
    )
    backend.write(instructions)
    status["outcome"] = "sent"

    if not blocking:
        return status

    if not backend.supports_read:
        # No need to wait for completion. The network backend doesn't support readback.
        return status

    while time.time() - start < 10:
        data = backend.read()
        if not data:
            time.sleep(0.005)
            continue
        try:
            result = interpret_response(data)
        except ValueError:
            logger.error(
                "TIME %.3f - Couln't understand response: %s",
                time.time() - start,
                data,
            )
            continue
        status["printer_state"] = result
        logger.debug("TIME %.3f - result: %s", time.time() - start, result)
        if result["errors"]:
            logger.error("Errors occured: %s", result["errors"])
            status["outcome"] = "error"
            break
        if result["status_type"] == "Printing completed":
            status["did_print"] = True
            status["outcome"] = "printed"
        if (
            result["status_type"] == "Phase change"
            and result["phase_type"] == "Waiting to receive"
        ):
            status["ready_for_next_job"] = True
        if status["did_print"] and status["ready_for_next_job"]:
            break

    if not status["did_print"]:
        logger.warning("'printing completed' status not received.")
    if not status["ready_for_next_job"]:
        logger.warning("'waiting to receive' status not received.")
    if (not status["did_print"]) or (not status["ready_for_next_job"]):
        logger.warning("Printing potentially not successful?")
    if status["did_print"] and status["ready_for_next_job"]:
        logger.info("Printing was successful. Waiting for the next job.")

    return status
