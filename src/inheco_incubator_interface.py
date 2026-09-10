"""
Python interface for controlling Inheco Single Plate Incubator Shaker devices, using the Inheco ComLib.dll.

Both the microplate and deep well versions of the Inheco Single Plate Incubator Shaker are supported.
"""

import argparse
import threading
import time
import traceback
from typing import Any, Optional

import clr
from madsci.client.event_client import EventClient


class Interface:
    """
    A Python interface for Inheco Single Plate Incubator Shakers.
    """

    def __init__(
        self,
        port: str,
        dll_path: Optional[
            str
        ] = r"C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll",
        logger: EventClient = None,
    ) -> None:
        """
        Opens the connection to the incubator.

        Args:
            port (str): COM port of the device(s).
            dll_path (str, optional): Path to Inheco ComLib.dll.

        Note:
            - No need to initialize here. Initialization is completed on startup of each module.
        """
        # Set up logger.
        self.port = port  # COM port of the device(s)
        self.logger = logger or EventClient()

        self.initialized_stack_floors = []

        self.lock = threading.Lock()
        clr.AddReference(dll_path)
        from IncubatorCom import Com

        self.incubator_com = Com()
        self.open_connection()

    # DEVICE CONTROL METHODS
    def open_connection(self) -> Any:
        """
        Opens the connection to the incubator(s) over the specified COM port.
        There may be several incubator devices in a stack on the same COM port.

        Returns:
            response (Any): Response code from the ComLib DLL. 77 = success, 170 = fail.
        """
        with self.lock:
            response = self.incubator_com.openCom(self.port)
            if response == 77:
                self.logger.log_info("COM connection opened successfully")
                print("COM connection opened successfully")  # noqa T201
            else:
                msg = (
                    f"Failed to open the Inheco incubator COM connection "
                    f"on port {self.port!r} (ComLib response code: {response!r}; "
                    f"77=success, 170=fail per docs)."
                )
                self.logger.log_warning(msg)
                raise Exception(msg)
            return response

    def close_connection(self) -> None:
        """
        Closes any existing open connection. No response expected on success or fail.
        """
        with self.lock:
            self.incubator_com.closeCom()
            self.logger.log_info("Connection closed.")

    def initialize_device(self, stack_floor: int) -> None:
        """
        Initializes the Inheco device through the open connection.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
        """
        self.send_message("AID", stack_floor=stack_floor, read_delay=3)
        self.initialized_stack_floors.append(stack_floor)
        self.logger.log_info(
            f"Inheco incubator initialized at stack floor {stack_floor}."
        )

    def reset_device(self, stack_floor: int) -> str:
        """
        Resets the Inheco device.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns: (str) Response from the device.
            The response seems to be 88 regardless of success or failure.
        """
        response = self.send_message("SRS", stack_floor=stack_floor, read_delay=5)
        self.logger.log_info("Device reset.")
        return response

    def report_error_flags(self, stack_floor: int) -> str:
        """
        Reports any error flags present on the device.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns:
            response (str): Error flags from the device. A response of "0" means no errors.
        """
        response = self.send_message("REF", stack_floor=stack_floor)
        self.logger.log_info(f"Error flags response: {response}")
        return response

    # TEMPERATURE CONTROL METHODS
    def get_actual_temperature(self, stack_floor: int) -> float:
        """
        Returns the actual temperature as measured by main sensor on incubator (sensor 1).
        Note: There are two other sensors that we don't report. Get their values with "RAT2" and "RAT3".

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns:
            temperature (float): Actual temperature in degrees Celsius.
        """
        response = self.send_message("RAT", stack_floor=stack_floor)
        temperature = float(response) / 10
        self.logger.log_info(f"Get actual temperature: {temperature}")
        return temperature

    def get_target_temperature(self, stack_floor: int) -> float:
        """
        Returns the set target temperature of the incubator.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns:
            temperature (float): Target temperature in degrees Celsius.
        """
        response = self.send_message("RTT", stack_floor=stack_floor)
        temperature = float(response) / 10
        self.logger.log_info(f"Get target temperature: {temperature}")
        return temperature

    def set_target_temperature(
        self,
        stack_floor: int,
        temperature: Optional[float] = 22.0,
    ) -> None | str:
        """
        Sets the target temperature.  If no temperature specified, temperature defaults to 22 deg Celsius.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
            temperature (float, optional): Temperature in degrees Celsius. Valid range is 0.0 to 80.0 deg C.

        Returns:
            response (str or None): Returns a string response if temperature input is valid, None otherwise.
        """
        if 0 <= (int(temperature * 10)) <= 800:
            self.logger.log_info(
                f"Setting target temperature to {int(temperature * 10)}."
            )
            message = "STT" + str(int(temperature * 10))
            return self.send_message(message, stack_floor=stack_floor)

        self.logger.log_warning(
            "Error: Temperature input invalid in set_target_temperature method."
        )
        return None

    def start_heater(self, stack_floor: int) -> None:
        """
        Enables the device heating element.
        Note: Read the set value with self.send_message("RHE"). 0 = off, 1 = on.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
        """
        self.send_message("SHE1", stack_floor=stack_floor)
        self.logger.log_info("Started heater.")

    def stop_heater(self, stack_floor: int) -> None:
        """
        Disables the device heating element.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
        """
        self.send_message("SHE", stack_floor=stack_floor)
        self.logger.log_info("Stopped heater.")

    def is_heater_active(self, stack_floor: int) -> bool:
        """
        Check state of heating element.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns:
            (bool) True if heater/cooler is activated, False otherwise.
        """
        response = self.send_message("RHE", stack_floor=stack_floor)

        try:
            response = int(response)
            if response == 0:  # 0 = off
                return False
            if response in [1, 2]:  # 1 = on, 2 = on with booster
                return True
            raise Exception("Unexpected integer response from is_heater_active query.")
        except Exception as e:
            self.logger.log_warning(
                f"Unable to parse is_heater_active response: {response}. {traceback.format_exc()}"
            )
            raise (e)

    # # DOOR CONTROL METHODS
    def open_door(self, stack_floor: int) -> None:
        """
        Opens the door in a safe way.

        1. Collect the state of every shaker, retrying failed state
        collections up to 3 times.
        2. Stop all shakers that were active.
        3. Attempt to open the door up to 3 times.
        4. Always restart any shakers that were stopped by this operation.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
        """

        retry_count = 3

        # Collect the shaker states for each initialized device -------
        shaker_states = {}
        for attempt in range(1, retry_count + 1):
            self.logger.log_info(
                f"Collecting shaker states, attempt " f"#{attempt}/{retry_count}"
            )

            print(f"INITIALIZED STACK FLOORS: {self.initialized_stack_floors}")

            for initialized_stack_floor in self.initialized_stack_floors:
                # Don't query shaker states we already know.
                if initialized_stack_floor in shaker_states:
                    continue

                # Query shaker states we don't know
                try:
                    is_shaking = self.is_shaker_active(
                        stack_floor=initialized_stack_floor
                    )
                    self.logger.log_info(
                        f"SHAKER STATUS = {is_shaking}, {type(is_shaking)}"
                    )  # TESTING
                    shaker_states[initialized_stack_floor] = is_shaking
                    # NOTE: is_shaking will return either true or false if the state was collected correctly,
                    # otherwise it will send an error.
                except Exception as e:
                    self.logger.log_warning(
                        f"Failed to collect shaker state for stack floor "
                        f"{initialized_stack_floor} on attempt "
                        f"#{attempt}/{retry_count}: {e}"
                    )

            # Stop checking shaker states once they have all been collected.
            if len(shaker_states) == len(self.initialized_stack_floors):
                break

            # Sleep before a retry  # TODO: necessary?
            if attempt < retry_count:
                time.sleep(2)

        # Make sure that all states were collected correctly
        missing_states = [
            floor
            for floor in self.initialized_stack_floors
            if floor not in shaker_states
        ]
        if missing_states:
            raise RuntimeError(
                "Failed to collect shaker state after "
                f"{retry_count} attempts. "
                f"Missing stack floor(s): {missing_states}"
            )

        self.logger.log_info(f"Final shaker states: {shaker_states}")

        # Stop all active shakers. -------
        stopped_shakers = []
        door_opened = False

        try:
            for attempt in range(1, retry_count + 1):
                self.logger.log_info(f"Open door attempt #{attempt}/{retry_count}")

                try:
                    # Stop all active shakers.
                    for shaker_stack_floor, is_shaking in shaker_states.items():
                        if is_shaking:
                            self.stop_shaker(
                                stack_floor=shaker_stack_floor
                            )  # returns nothing, nothing to check.
                            stopped_shakers.append(shaker_stack_floor)
                            self.logger.log_info(
                                f"Stopped shaker at stack floor {shaker_stack_floor}"
                            )
                            time.sleep(5)  # wait for the shaker to stop
                            # TODO: Move the sleep out of the for loop?

                    # Attempt to open the door
                    self.send_message(
                        message_string="AOD",
                        stack_floor=stack_floor,
                        read_delay=6,
                    )
                    time.sleep(5)  # wait for the door to open

                    # Check if the door has opened
                    door_status = self.report_door_status(stack_floor=stack_floor)
                    # NOTE: Will return response regardless of if the door status is collected correctly
                    if door_status == "1":
                        self.logger.log_info("Door opened successfully.")
                        door_opened = True
                        break

                    self.logger.log_warning(
                        f"Failed to open door successfully at stack floor "
                        f"{stack_floor}. Door status={door_status}"
                    )

                except Exception as e:
                    # log failed door open attempt
                    self.logger.log_warning(
                        f"Open door attempt #{attempt}/{retry_count} " f"failed: {e}"
                    )

                # sleep before next open_door attempt
                if attempt < retry_count:
                    time.sleep(2)

            # Raise exception if door failed to open after 3 attempts
            if not door_opened:
                raise RuntimeError(
                    f"Failed to open door at stack floor {stack_floor} "
                    f"after {retry_count} attempts"
                )

        finally:
            restart_successes = set()
            restart_errors = []

            for shaker_stack_floor in stopped_shakers:
                # Don't restart the shaker with the open door.
                if shaker_stack_floor == stack_floor:
                    continue

                # Try to restart the shakers.
                for attempt in range(1, retry_count + 1):
                    try:
                        self.logger.log_info(
                            f"Restarting shaker at stack floor {shaker_stack_floor}, "
                            f"attempt #{attempt}/{retry_count}"
                        )

                        # Restart the shaker and wait.
                        self.start_shaker(stack_floor=shaker_stack_floor)
                        time.sleep(5)  # TODO: is this enough time?

                        # Verify that the shaker actually restarted.
                        if self.is_shaker_active(stack_floor=shaker_stack_floor):
                            restart_successes.add(shaker_stack_floor)
                            self.logger.log_info(
                                f"Confirmed shaker restarted at stack floor "
                                f"{shaker_stack_floor} on attempt #{attempt}"
                            )
                            break

                        self.logger.log_warning(
                            f"Shaker at stack floor {shaker_stack_floor} "
                            f"did not restart on attempt #{attempt}"
                        )

                    except Exception as e:
                        restart_errors.append((shaker_stack_floor, e))
                        self.logger.log_warning(
                            f"Failed to restart shaker at stack floor "
                            f"{shaker_stack_floor} on attempt "
                            f"#{attempt}/{retry_count}: {e}"
                        )

                # Move on to the next shaker regardless of whether this one succeeded.
                if shaker_stack_floor not in restart_successes:
                    self.logger.log_warning(
                        f"Shaker at stack floor {shaker_stack_floor} "
                        f"failed to restart after {retry_count} attempts"
                    )

            # Determine which shakers needed restarting but were not successfully restarted.
            shakers_needing_restart = {
                shaker_stack_floor
                for shaker_stack_floor in stopped_shakers
                if shaker_stack_floor != stack_floor
            }

            failed_restarts = shakers_needing_restart - restart_successes

            if failed_restarts:
                raise RuntimeError(
                    "Failed to restart shaker(s) at stack floor(s): "
                    f"{sorted(failed_restarts)}"
                )

    def close_door(self, stack_floor: int) -> None:
        """
        Closes the door.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
        """
        self.send_message(
            "ACD",
            stack_floor=stack_floor,
            read_delay=7,
        )
        self.logger.log_info("Closed door.")

    def report_door_status(self, stack_floor: int) -> str:
        """
        Determines if incubator door is open.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns: (str) Response from device.
            Responses:
                0 = door closed
                1 = door open
        """
        response = self.send_message("RDS", stack_floor=stack_floor)
        self.logger.log_info(f"Door status (0 closed, 1 open): {response}")
        return response

    def report_labware(self, stack_floor: int) -> str:
        """
        Determines if labware is present in incubator.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns: (str) Response from device.
            Responses:
                0 = no labware present
                1 = labware detected
                8 = error, door open
                7 = error, reset and door closed
        """
        response = self.send_message("RLW", stack_floor=stack_floor)
        self.logger.log_info(f"Report labware response: {response}")
        return response

    # SHAKER CONTROL METHODS
    def start_shaker(self, stack_floor: int, status: Optional[str] = "ND") -> None:
        """
        Enables the device shaking element.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
            status: (str, optional): "1" = on, (str) "ND" = on without labware detection.
        """
        if status in [1, "1", "ND"]:
            self.send_message(
                "ASE" + str(status), stack_floor=stack_floor, read_delay=8
            )
            self.logger.log_info(f"Started shaker at stack floor {stack_floor}.")
        else:
            self.logger.log_warning(
                f"Value Error: Invalid status in start_shaker method, stack floor {stack_floor}."
            )
            raise ValueError(
                f"Invalid status in start_shaker method, stack floor {stack_floor}."
            )

        # time.sleep(8)

        # # Check that shaker is active after starting shaker
        # shaker_status = self.is_shaker_active(stack_floor=stack_floor)
        # if not shaker_status:
        #     raise Exception(f"Could not confirm shaker started on stack floor {stack_floor}")

    def smart_start_shaker(
        self, stack_floor: int, status: Optional[str] = "ND"
    ) -> None:
        self.logger.log_info("SMART START SHAKER CALLED!!!!!!!!!!")

        retry_count = 3
        shaker_states = {}

        # Try 3 times to collect all shaker states
        for attempt in range(1, retry_count + 1):
            self.logger.log_info(
                f"Collecting shaker states, attempt " f"#{attempt}/{retry_count}"
            )

            for initialized_stack_floor in self.initialized_stack_floors:
                # Don't query shaker states we already know.
                if initialized_stack_floor in shaker_states:
                    continue

                # Query shaker states we don't know
                try:
                    is_shaking = self.is_shaker_active(
                        stack_floor=initialized_stack_floor
                    )
                    self.logger.log_info(
                        f"SHAKER STATUS = {is_shaking}, {type(is_shaking)}"
                    )  # TESTING
                    shaker_states[initialized_stack_floor] = is_shaking
                    # NOTE: is_shaking will return either true or false if the state was collected correctly,
                    # otherwise it will send an error.
                except Exception as e:
                    self.logger.log_warning(
                        f"Failed to collect shaker state for stack floor "
                        f"{initialized_stack_floor} on attempt "
                        f"#{attempt}/{retry_count}: {e}"
                    )

            # Stop checking shaker states once they have all been collected.
            if len(shaker_states) == len(self.initialized_stack_floors):
                break

            # Sleep before a retry  # TODO: necessary?
            if attempt < retry_count:
                time.sleep(2)

        # Make sure that all states were collected correctly
        missing_states = [
            floor
            for floor in self.initialized_stack_floors
            if floor not in shaker_states
        ]
        if missing_states:
            raise RuntimeError(
                "Failed to collect shaker state after "
                f"{retry_count} attempts. "
                f"Missing stack floor(s): {missing_states}"
            )

        self.logger.log_info(f"Final shaker states: {shaker_states}")

        # Stop all active shakers. -------
        stopped_shakers = []
        shaker_started = False

        try:
            for attempt in range(1, retry_count + 1):
                self.logger.log_info(f"Smart start shaker #{attempt}/{retry_count}")

                try:
                    # Stop all active shakers.
                    for shaker_stack_floor, is_shaking in shaker_states.items():
                        if is_shaking:
                            self.stop_shaker(
                                stack_floor=shaker_stack_floor
                            )  # returns nothing, nothing to check.
                            stopped_shakers.append(shaker_stack_floor)
                            self.logger.log_info(
                                f"Stopped shaker at stack floor {shaker_stack_floor}"
                            )
                            time.sleep(5)  # wait for the shaker to stop
                            # TODO: Move the sleep out of the for loop?

                            # TODO: Actually check that the shaker has stopped here?????!!!!!

                    # Start the shaker at the desired stack floor
                    self.start_shaker(stack_floor=stack_floor)

                    time.sleep(5)

                    # check that shaker started at specified stack floor
                    shaker_status = self.is_shaker_active(stack_floor=stack_floor)
                    if shaker_status:
                        # Break if the shaker restarted correctly
                        shaker_started = True
                        self.logger.log_info(
                            f"Confirmed shaker restarted at stack floor "
                            f"{shaker_stack_floor} on attempt #{attempt}"
                        )
                        break

                except Exception as e:
                    # log failed door open attempt
                    self.logger.log_warning(
                        f"Open door attempt #{attempt}/{retry_count} " f"failed: {e}"
                    )

                # sleep before next open_door attempt
                if attempt < retry_count:
                    time.sleep(2)

            # Raise exception if door failed to open after 3 attempts
            if not shaker_started:
                raise RuntimeError(
                    f"Failed to start shaker at {stack_floor} "
                    f"after {retry_count} attempts"
                )

        finally:
            restart_successes = set()
            restart_errors = []

            for shaker_stack_floor in stopped_shakers:
                # Don't restart the shaker that is already running/
                if shaker_stack_floor == stack_floor:
                    continue

                # Try to restart the shakers.
                for attempt in range(1, retry_count + 1):
                    try:
                        self.logger.log_info(
                            f"Restarting shaker at stack floor {shaker_stack_floor}, "
                            f"attempt #{attempt}/{retry_count}"
                        )

                        # Restart the shaker and wait.
                        self.start_shaker(stack_floor=shaker_stack_floor)
                        time.sleep(5)  # TODO: is this enough time?

                        # Verify that the shaker actually restarted.
                        if self.is_shaker_active(stack_floor=shaker_stack_floor):
                            restart_successes.add(shaker_stack_floor)
                            self.logger.log_info(
                                f"Confirmed shaker restarted at stack floor "
                                f"{shaker_stack_floor} on attempt #{attempt}"
                            )
                            break

                        self.logger.log_warning(
                            f"Shaker at stack floor {shaker_stack_floor} "
                            f"did not restart on attempt #{attempt}"
                        )

                    except Exception as e:
                        restart_errors.append((shaker_stack_floor, e))
                        self.logger.log_warning(
                            f"Failed to restart shaker at stack floor "
                            f"{shaker_stack_floor} on attempt "
                            f"#{attempt}/{retry_count}: {e}"
                        )

                # Move on to the next shaker regardless of whether this one succeeded.
                if shaker_stack_floor not in restart_successes:
                    self.logger.log_warning(
                        f"Shaker at stack floor {shaker_stack_floor} "
                        f"failed to restart after {retry_count} attempts"
                    )

            # Determine which shakers needed restarting but were not successfully restarted.
            shakers_needing_restart = {
                shaker_stack_floor
                for shaker_stack_floor in stopped_shakers
                if shaker_stack_floor != stack_floor
            }

            failed_restarts = shakers_needing_restart - restart_successes

            if failed_restarts:
                raise RuntimeError(
                    "Failed to restart shaker(s) at stack floor(s): "
                    f"{sorted(failed_restarts)}"
                )

        # time.sleep(8)

        # # Check that shaker is active after starting shaker
        # shaker_status = self.is_shaker_active(stack_floor=stack_floor)
        # if not shaker_status:
        #     raise Exception(f"Could not confirm shaker started on stack floor {stack_floor}")

    def stop_shaker(self, stack_floor: int) -> None:
        """
        Disables the device shaking element.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.
        """
        self.send_message("ASE0", stack_floor=stack_floor, read_delay=5)
        self.logger.log_info("Stopped shaker.")

    def is_shaker_active(self, stack_floor: int) -> bool:
        """
        Determines if incubator shaker is active.

        Args:
            stack_floor (int): Stack floor of the Inheco incubator device.

        Returns: (bool) Status of shaker.
            True if shaker is active
            False if shaker not active
        """
        response = self.send_message("RSE", stack_floor=stack_floor)
        try:
            response = int(response)
            if response in [0, 2]:
                # response 2 means shaker is switched off but still moving
                self.logger.log_info("Shaker is inactive.")
                return False
            if response == 1:
                self.logger.log_info("Shaker is active.")
                return True
            self.logger.log_warning(
                f"Unable to read shaker state: response = {response}."
            )
            raise Exception("Unable to read shaker state.")
        except Exception as e:
            self.logger.log_warning(
                f"Unable to parse is_shaker_active response: {response}."
            )
            raise (e)

    def set_shaker_parameters(
        self,
        stack_floor: int,
        amplitude: Optional[float] = 2.0,
        frequency: Optional[float] = 14.2,
    ) -> None:
        """
        Sets the shaking parameters.

        Args:
            amplitude: (float) Shaking distance in mm, 0.0-3.0 mm valid, 2.0 mm default.
            frequency: (float) Speed of shaking revolutions in Hz (1Hz = 60 rpm), 6.6-30.0 Hz valid, 14.2 default Hz.

        Notes:
        - Through the dll, there is support for controlling amplitude and frequency on x and y axes. That level of control was not deemed necessary for our applications and is not supported in this Python interface.
        - Phase shift is also controllable through dll, we will keep it at 0 deg.
        - Read set values with: "RFX" (frequency x), "RFY" (frequency y), "RAX" (amplitude x), "RAY" (amplitude y), and "RPS" (phase shift)
        - Read actual values with: "RFX1", "RFY1", "RAX(1(actual) or 2(static measure))", "RAY(1(actual) or 2(static measure))", and "RPS1"
        """
        phase_shift = "000"

        # Format the inputs.
        try:
            amplitude = int(amplitude * 10)
            frequency = int(frequency * 10)

            if 0 <= amplitude <= 30 and 66 <= frequency <= 300:
                # Message formatting = SSP + str(amplitude_x) + srt(amplitude_y) + str(frequency_x) + str(frequency_y) + str(phase_shift)
                self.send_message(
                    "SSP"
                    + str(amplitude)
                    + ","
                    + str(amplitude)
                    + ","
                    + str(frequency)
                    + ","
                    + str(frequency)
                    + ","
                    + str(phase_shift),
                    stack_floor=stack_floor,
                )
                self.logger.log_info("Shaker parameters set.")
            else:
                self.logger.log_warning(
                    "Error: Invalid amplitude or frequency input values in set_shaker_parameters method."
                )

        except Exception as e:
            self.logger.log_warning(f"Error: Unable to set shaker parameters. {e}")
            self.logger.log_warning(traceback.format_exc())
            raise e

    # HELPER METHODS
    def send_message(
        self,
        message_string: str,
        device_id: Optional[int] = 2,
        stack_floor: Optional[int] = 0,
        read_delay: Optional[float] = 0.5,
    ) -> str:
        """
        Formats and sends message to Inheco device, then collects device response.

        Args:
            message_string: (str) Message to send to Inheco device.
            device_id: (int) ID of the Inheco device that will receive the message, default 2.
            stack_floor: (int) Level of the Inheco device. Need to specify in case several devices are stacked, default 0.
            read_delay: (float) Seconds to wait before reading COM response, default .5 seconds.

        Returns:
            formatted_response (str): Response from the COM port without extra characters.
        """
        with self.lock:
            # Convert message length, device ID, and stack floor to bytes.
            bytes_message_length = len(message_string) & 0xFF
            bytes_device_id = device_id & 0xFF
            bytes_stack_floor = stack_floor & 0xFF

            # Convert them message to byte array.
            bytes_message = bytes([ord(c) for c in message_string])

            # Format the message, send over COM port and collect response.
            self.incubator_com.sendMsg(
                bytes_message, bytes_message_length, bytes_device_id, bytes_stack_floor
            )
            self.logger.log_debug(
                f"Sent message: bytes_message={bytes_message}, bytes_message_length={bytes_message_length}, bytes_device_id={bytes_device_id}, bytes_stack_floor={bytes_stack_floor}"
            )

            time.sleep(read_delay)

            # Read the COM port response.
            response = self.incubator_com.readCom()
            self.logger.log_debug(f"sent message response: {response}")
            formatted_response = self.format_response(response)
            self.logger.log_debug(
                f"sent message formatted response: {formatted_response}"
            )

            return formatted_response

    def format_response(self, response: str) -> str:
        """
        Extracts the important message details from longer COM response message.

        Args:
            response: (str) Raw response from the COM port after a message is sent.

        Returns:
            formatted_response: (str) Response from the COM port without extra characters.

        Note:
            - The extra characters relate to device ID. They are not needed.
        """
        try:
            # Remove extra characters.
            formatted_response = response[1:]
            formatted_response = formatted_response[:-4]

        except Exception as e:
            self.logger.log_info(
                f"Device response ({response} could not be formatted. {e}"
            )

        # Check for '#' response, meaning invalid command was sent.
        if formatted_response == "#":
            self.logger.log_info("Error: invalid command sent, '#' response received.")
            raise Exception("Invalid command sent, '#' response received.")

        return formatted_response

    @property
    def is_busy(self) -> bool:
        """
        Determines if the incubator interface is busy processing a command.

        Returns:
            (bool): True if incubator busy, False otherwise.
        """
        return bool(self.lock.locked())


if __name__ == "__main__":
    # Argparser for command line execution.
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--device",
        type=str,
        help="Serial port for communicating with the device",
        default="COM6",
    )
    argparser.add_argument(
        "--dll_path",
        type=str,
        help="Path to Inheco device dll",
        default="C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll",
    )
    args = argparser.parse_args()
    device = args.device
    dll_path = args.dll_path

    com = Interface(port=device, dll_path=dll_path)
    print(f"Inheco incubator device connected, {device}.")  # noqa T201
