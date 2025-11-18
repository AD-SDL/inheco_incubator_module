# Inheco Single Plate Incubator Shaker Module

A MADSci-powered module for controlling Inheco Single Plate Incubator Shakers, both the microplate and deep well plate versions.

Contains an Inheco incubator interface (inheco_incubator_interface.py), a FastAPI wrapper for the interface functions (inheco_interface_FastAPI_wrapper.py), and an Inheco incubator REST node (inheco_incubator_rest_node.py).

### General notes on structure

Inheco incubators can be stacked on top of each other. The bottom device is connected to power and the computer over a COM port. All other devices in the stack are ultimately connected through master-slave serial communication to the bottom device. Thus, only the COM port and device ID of the bottom device are required to send commands to all devices in the same stack. Stack floor is used to differentiate the incubators in a stack, with the bottom device having a stack floor of 0, the device above that having a stack floor of 1, and so on until the top of the stack.

You could have multiple stacks of incubators following this same pattern.


### Installation

Inheco incubators run on Windows systems. See device documentation on system requirements for more details.

Before using Inheco incubator(s), you will need to clone the module GitHub repo and install the dependencies in a virtual environment. Use the code below to complete this step.

General install instructions:

    # Clone the repository
    git clone https://github.com/AD-SDL/inheco_incubator_module.git
    cd inheco_incubator_module

    # Create and activate a Python virtual environment
    python -m venv .venv
    .venv\Scripts\activate

    # Install the dependencies
    pip install -e .

### Running the interface

The Inheco incubator interface connects to the entire stack (one or multiple devices) over the COM port of the master device and can be used to send commands to any device in the stack.

Test the interface connection with the command below:

    python your\\path\\to\\inheco_incubator_interface.py --device <(optional) your COM port> --dll_path <(optional) path to incubator control dll (ComLib.dll)>

--device will default to "COM5" and -dll_path will default to "C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll".

Example usage with no optional arguments:

    python inheco_incubator_interface.py

Example usage with optional device argument:

    python inheco_incubator_interface.py --device "COM5" --dll_path "C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll"

This will print "Inheco incubator device connected" along with the specified COM port if the interface is able to connect correctly to the device.

You can also use this Python interface in other programs. The link below shows an example Python program which uses the Inheco interface to demonstrate all functions available in the interface.

[Example interface usage](https://github.com/AD-SDL/inheco_incubator_module/blob/main/examples/interface_usage_example.py)


### Running the FastAPI Interface Wrapper

The FastAPI wrapper instantiates a singleton instance of the Inheco incubator interface and allows commands to be sent to each device in the stack through HTTP communication.

If you plan to run each device through a WEI REST module, you will need to start the FastAPI server before starting one WEI node for each device.

Start the FastAPI Server with the command below:

    python your\\path\\to\\inheco_interface_FastAPI_wrapper.py --host <(optional) host computer IP for the interface API> --device <(optional) COM Port for the incubator device(s)> --port <(optional) Port to run FastAPI on> --dll_path <(optional) path to incubator control dll (ComLib.dll)>.


--host will default to "0.0.0.0", --device will default to "COM5", --port will default to 7000, and dll_path will default to "C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll".

Example usage with no optional arguments:

    python inheco_interface_FastAPI_wrapper.py

Example usage with all optional arguments:

    python inheco_interface_FastAPI_wrapper.py --host "0.0.0.0" --device "COM5" --port 7000 --dll_path "C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll"

Once the FastAPI Wrapper is running, you can go to the docs of your server to test out commands. For example, if all defaults were unchanged, you could go to http://localhost:7000/docs to see a list of all commands and example usage.

### Running the REST Node

If you would like to run these devices through MADSci, you will need to start one MADSci REST Node for each individual device, even if they are in the same stack.

Each MADSci REST Node can be started with a command in the format below, making sure to adjust the stack floor and node_url arguments for each device:

    python your\\path\\to\\inheco_incubator_module.py --node_url <(optional str) address for your incubator MADSci REST Node>> --device_id <(optional int) device ID of the Inheco incubator device> --stack_floor <(optional int) stack floor of the Inheco incubator device> --interface_host <(optional str) Inheco Interface FastAPI server host> --interface_port <(optional int) Inheco Interface FastAPI server port> 

--node_url will default to "http://127.0.0.1:2000", --device_id will default to 2, --stack_floor will default to 0, --interface_host will default to 127.0.0.1, and --interface_port will default to 7000 unless specified.

Example usage with no optional arguments (assumes no changes needed to defaults):

    python inheco_incubator_module.py

Example usage with all optional arguments:

    python inheco_incubator_module.py --node_url "http://127.0.0.1:3005" --device_id 2 --stack_floor 0 --interface_host "localhost" --interface_port 7000 


### Example Usage in WEI Workflow YAML file

The link below shows an example of a YAML MADSci Workflow file that could interact with the Inheco Single Plate Incubator Shaker module.

[Example MADSci usage](https://github.com/AD-SDL/inheco_incubator_module/blob/main/examples/example_madsci_workflow.yaml)
