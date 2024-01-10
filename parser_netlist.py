import os
import re
from dotenv import load_dotenv
import logging
# import networkx as nx
# import matplotlib.pyplot as plt
# import numpy as np
import json
import pickle

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(filename='verilog_parser.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class VerilogModule:
    """
    Verilog Module class to represent a module in the design.
    """
    def __init__(self, name):
        self.name = name
        self.ports = {"input": [], "output": []}
        self.instances = []
        self.nets = []

    def __str__(self):
        return f"Module: {self.name}"

    def to_dict(self):
            return {
                "module_name": self.name,
                "ports": {direction: [port.to_dict() for port in ports] for direction, ports in self.ports.items()},
                "instances": [instance.to_dict() for instance in self.instances],
                "nets": [net.to_dict() for net in self.nets],             
            }

class VerilogInstance:
    '''
    Verilog Instance object that represents an instance of another verilog module or a Library cell such as
    BUFF, XOR etc.
    '''
    def __init__(self, name, cell_type, ref_name):
        self.name = name
        self.cell_type = cell_type
        self.ref_name = ref_name
        self.pins = []

    def __str__(self):
        return f"Instance: {self.name}, Cell Type: {self.cell_type}, Reference: {self.ref_name}"

    def to_dict(self):
        return {
            "instance": self.name,
            "cell_type": self.cell_type,
            "ref_name": self.ref_name,
            "pins": [pin.to_dict() for pin in self.pins]
        }

class VerilogNet:
    '''
    Verilog Net object that represents the connection between a port and an Instance pin or between two different Instances(pins) 
    '''
    def __init__(self, name, net_type, width):
        self.name = name
        self.net_type = net_type
        self.width = self.parse_width(width)

    @staticmethod
    def parse_width(width_str_or_tuple):
        '''
        Parses a width specification from a string or tuple into a tuple of integers.

        It can accept either a string in the format '[x:y]' or a tuple.
        If the input is a string, it strips the brackets and whitespace, then splits the string
        at the colon to create a tuple of integers. If the input is already a tuple, it returns
        it directly. If the input is None or an empty string, it returns None.

        Args:
            width_str_or_tuple (str or tuple): The width specification to be parsed. It can be
                                               a string in the format '[x:y]' or a tuple (x, y).

        Returns:
            tuple or None: A tuple of two integers representing the parsed width (x, y) if the
                           input is a valid width specification. Returns None if the input is
                           None, an empty string, or an invalid format.

        Example:
            parse_width('[3:0]') returns (3, 0)
            parse_width((5, 1)) returns (5, 1)
            parse_width(None) returns None
        '''
        if isinstance(width_str_or_tuple, tuple):
            return width_str_or_tuple
        if width_str_or_tuple:
            # Strip the brackets and whitespace, then split it
            return tuple(map(int, width_str_or_tuple.strip('[] ').split(':')))
        return None

    def __str__(self):
        width_str = f"[{self.width[0]}:{self.width[1]}]" if self.width else ""
        return f"Net: {self.name}, Type: {self.net_type}, Width:{width_str}"

    def to_dict(self):
        return {
            "name": self.name,
            "net_type": self.net_type,
            "width": self.width
        }

class VerilogPin:
    '''
    Verilog Pin objects that represents the pins of a VerilogInstance object,
    which connects the instance to other instances or ports through VerilogNet objects
    '''
    def __init__(self, name, instance, net, direction=None):
        self.name = name
        self.direction = direction
        self.instance = instance
        self.net = net

    def __str__(self):
        net_str = self.net.name if self.net else "None"
        return f"Pin: {self.name}, Connected to: {net_str}"

    def to_dict(self):
        return {
            "name": self.name,
            "direction": self.direction,
            "instance": self.instance.name if self.instance else None,
            "net": self.net.name if self.net else None
        }

class VerilogPort:
    '''
    Verilog Port Objects that represent the ports in a Module, such as input/output.
    '''
    def __init__(self, name, direction, width=None):
        self.name = name
        self.direction = direction
        self.width = VerilogNet.parse_width(width)
        self.net = []

    def __str__(self):
        width_str = f"[{self.width[0]}:{self.width[1]}]" if self.width else ""
        return f"Port: {self.name}, Direction: {self.direction}, Width: {width_str}"

    def to_dict(self):
        return {
            "name": self.name,
            "direction": self.direction,
            "width": self.width
        }

# Precompiled regex patterns
MODULE_PATTERN = re.compile(r'module (\w+)\s*\(')
PORT_PATTERN = re.compile(r'(input|output)\s*(?:\[(\d+:\d+)\])?\s*([^;]+);', re.DOTALL)
NET_PATTERN = re.compile(r'wire\s+((?:\[\d+:\d+\])?\s*\w+\s*(?:,\s*\w+\s*)*);', re.DOTALL)
INSTANCE_PATTERN = re.compile(r'^\s*(\w+)\s+(\w+)\s*\((?!\s*input\s|\s*output\s|\s*inout\s)')
PIN_PATTERN = re.compile(r'\.(\w+)\(([^)]+)\)')

def verify_instance_declaration(instance, module_templates):
    """
    Verifies whether an instance declaration is valid based on the module templates.
    If the instance is not found in the templates, it is considered a leaf-level instance.

    Args:
        instance (dict): The instance declaration.
        module_templates (list): A list of module templates.

    Returns:
        bool: True if the instance declaration is valid, False otherwise.

    Raises:
        TypeError: If the input arguments are not of the expected type.
        KeyError: If required keys are missing in the input dictionaries.
    """
    # Function Implementation
    
    logging.debug('Verifying instance declaration for instance: %s, %s', instance['ref_name'], instance['name'])
    print(f'Verifying instance declaration for instance: {instance["ref_name"]}, {instance["name"]}')

    if not isinstance(instance, dict) or not isinstance(module_templates, list):
        logging.error("Invalid input types for instance or module_templates. Instance type: %s, Module templates type: %s", type(instance).__name__, type(module_templates).__name__)
        print(f"Invalid input types for instance or module_templates. Instance type: {type(instance).__name__}, Module templates type: {type(module_templates).__name__}")
        raise TypeError("Invalid input types for instance or module_templates.")

    try:
        template = next((t for t in module_templates if t['name'] == instance['ref_name']), None)
        
        if not template:
            logging.info("Instance %s is a leaf-level instance or a library cell.", instance['name'])
            print(f"Instance {instance['name']} is a leaf-level instance or a library cell.")
            return True

        template_ports = {port['name']: port for direction in template['ports'] for port in template['ports'][direction]}
        for pin in instance['pins']:
            pin_name = pin['name']
            if pin_name not in template_ports:
                logging.error("Port %s in instance %s is not defined in module %s.", pin_name, instance['name'], template['name'])
                print(f"Error: Port {pin_name} in instance {instance['name']} is not defined in module {template['name']}.")
                return False

        logging.info("Instance %s verified successfully.", instance['name'])
        print(f"Instance {instance['name']} verified successfully.")
        return True

    except KeyError as e:
        logging.error("Missing key in instance or module template: %s", e)
        print(f"Missing key in instance or module template: {e}")
        raise KeyError(f"Missing key in instance or module template: {e}")

def parse_netlist_hierarchy_module_template(file_path):
    """
    Parses a Verilog netlist file to extract module templates, including their names and port definitions.

    This function reads a Verilog netlist file and identifies all module definitions within it. For each module,
    it extracts the module's name and its ports, including their names, directions (input/output), and optionally
    their widths. The function constructs a list of module templates, where each template is a dictionary
    containing the module's name and a dictionary of its ports categorized by direction.

    Args:
        file_path (str): The path to the netlist file to be parsed.

    Returns:
        module_templates (list of dict): A list of dictionaries, each representing a module template. 
                                         Each dictionary contains the module's name and a dictionary of its ports. 
                                         The ports dictionary categorizes ports into 'input' and 'output', with each entry being a list of 
                                         port information dictionaries.
                                         Each port information dictionary contains the port's name and optionally its width.

    Raises:
        FileNotFoundError: If the specified file_path does not exist.
        Exception: If the number of 'module' declarations does not match the number of 'endmodule' declarations,
                   indicating a potential syntax error in the netlist file.

    Note:
        The function uses regular expressions to identify module declarations and port definitions. It assumes
        a specific format for these declarations as per standard Verilog syntax. The function also prints the
        name of each module found during the parsing process.
    """
    # Function Implementation
    print('\ndef parse_netlist_hierarchy_module_template: is called.\n')
    logging.info("def parse_netlist_hierarchy_module_template is called.")
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logging.error("The file at %s was not found.",file_path)
        raise FileNotFoundError(f"The file at {file_path} was not found.")

    module_templates = []  # List to store the module templates
    module_count = 0       # Counter for the number of 'module' declarations
    endmodule_count = 0    # Counter for the number of 'endmodule' declarations
    current_module = None  # Flag to indicate if currently parsing a module
    current_module_ports = {}  # Dictionary to store ports of the current module

    for line in lines:
        line = line.strip()  # Remove leading and trailing whitespaces

        if line.startswith('//') or not line:
            # Skip comments and empty lines
            continue

        module_match = re.search(MODULE_PATTERN, line)
        if module_match:
            module_name = module_match.group(1)  # Extract the module name
            module_count += 1
            current_module = module_name  # Set current module name
            current_module_ports = {}  # Initialize ports dictionary for the new module
            # print(f"Module found: {module_name}")
            logging.debug("Module found: %s",module_name)
            continue

        if current_module:
            # Parse ports within the module
            port_matches = PORT_PATTERN.findall(line)
            for direction, width, port_names in port_matches:
                # Split port names by commas and strip whitespace
                port_names = [name.strip() for name in port_names.split(',')]
                for port_name in port_names:
                    logging.info("Port Found : %s", port_name)
                    port_info = {
                        "name": port_name,
                        "width": width.strip() if width else None  # Strip whitespace from width if it exists
                    }
                    # Add the port to the current module's ports dictionary
                    current_module_ports.setdefault(direction, []).append(port_info)


            if line.startswith("endmodule"):
                endmodule_count += 1
                # Add the parsed module to the module templates list
                module_templates.append({
                    "name": current_module,
                    "ports": current_module_ports
                })
                current_module = None  # Reset current module

    # Check if the number of module and endmodule declarations match
    if module_count != endmodule_count:
        logging.error("Mismatch in the number of 'module' and 'endmodule' declarations in the file.")
        raise Exception("Mismatch in the number of 'module' and 'endmodule' declarations in the file.")

    return module_templates

def validate_instances(lines, module_templates):
    """
    Parses instance declarations from a list of netlist lines and verifies each instance.

    This function iterates through each line of the netlist, searching for instance declarations.
    For each instance found, it extracts the instance name, ref_name, and pin connections.
    It then verifies the instance against the provided module templates. If the instance matches
    a module template, it checks if the instance's ports correspond to the template's ports.
    Instances not found in the module templates are considered valid, assuming they are leaf-level
    instances or library cells.

    Args:
        lines (list of str): The lines of the netlist file.
        module_templates (list of dict): A list of parsed module templates. Each template is a dictionary
                                         containing the module name and its ports.

    Returns:
        list of dict: A list of verified instances. Each instance is represented as a dictionary
                      containing the instance name, ref_name, and a list of pins. Each pin is
                      also a dictionary containing the pin name and the connected net.
    
    Raises:
        ValueError: If an instance declaration is malformed or cannot be parsed correctly.

    Note:
        The function prints a message for each invalid instance declaration it encounters.
    """
    # Function Implementation
    
    print('\ndef validate_instances: is called.\n')
    logging.info('defvalidate_instances function called.')

    instances = []  # Initialize an empty list to store instances

    # Iterate through each line in the netlist
    for line in lines:
        # Search for instance declarations in the line
        instance_match = INSTANCE_PATTERN.search(line)
        if instance_match:
            # Extract ref_name and instance name from the match
            ref_name, name = instance_match.groups()

            if ref_name == 'module':
                continue

            try:
                # Find all pin connections for this instance
                pins = PIN_PATTERN.findall(line)

                # Create a dictionary for the instance with its details
                instance = {
                    'name': name,
                    'ref_name': ref_name,
                    'pins': [{'name': pin, 'net': net} for pin, net in pins]
                }

                # Verify the instance against the module templates
                if verify_instance_declaration(instance, module_templates):
                    # If valid, add the instance to the instances list
                    instances.append(instance)
                    logging.info("Verified instance: %s", name)
                    print(f"Verified instance: {name}")
                else:
                    # If invalid, log and print an error message
                    logging.error("Invalid instance declaration: %s", name)
                    print(f"Invalid instance declaration: {name}")
            except Exception as e:
                error_message = f"Error parsing instance declaration in line: '{line}'. Error: {e}"
                logging.error(error_message)
                print(error_message)
                raise ValueError(error_message)

    return instances  # Return the list of verified instances

def determine_cell_type(ref_name, module_templates):
    # Define your logic to determine cell type based on reference name
    # For example, if the reference name matches the module name, it's hierarchical, otherwise, it's leaf-level
    if any(ref_name.lower() == template['name'].lower() for template in module_templates):
        return 'hierarchical'
    else:
        return 'leaf-level'

def parse_netlist(file_path, modules_templates):
    """
    Parses a Verilog netlist file and constructs a list of VerilogModule objects.

    This function reads a Verilog netlist file and extracts information about modules,
    ports, nets, and instances within each module. It creates VerilogModule objects,
    each containing details about its ports, nets, and instances. The function handles
    module declarations, port definitions, net declarations, and instance declarations,
    including the connections of instance pins to nets or constants.

    Args:
        file_path (str): The path to the Verilog netlist file.

    Returns:
        List[VerilogModule]: A list of VerilogModule objects representing the modules
                             found in the netlist file. Each module object contains
                             detailed information about its internal structure.
    """

    # Function Implementation
    
    print('\ndef parse_netlist: is called.\n')
    logging.info('parse_netlist function called.')

    modules = []  # List to store the VerilogModule objects
    current_module = None  # Current module being parsed
    inside_instance = False  # Flag to track if we are parsing inside an instance
    instance = None  # Current instance being parsed

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        modules = []
        current_module = None
        inside_instance = False
        instance = None

        for line in lines:

            if line.strip().startswith('//') or not line:
                continue
            
            # Check for module declaration
            if line.strip().startswith('module'):
                module_name = MODULE_PATTERN.search(line).group(1)
                print(f"Module found : {module_name}")
                logging.debug("Module found : %s", module_name)
                current_module = VerilogModule(module_name)
                modules.append(current_module)
                continue  # Skip to the next line

            # If we are inside a module, parse its contents
            if current_module:

                # Parse ports
                port_matches = PORT_PATTERN.findall(line)
                for port_match in port_matches:
                    direction, width, port_names = port_match[0], port_match[1], port_match[2]
                    # Split port names by commas and strip whitespace
                    port_names = [name.strip() for name in port_names.split(',')]
                    for port_name in port_names:
                        if width:
                            print(f"{direction} Port found : {port_name} width {width}")
                            logging.debug("%s Port found : %s width %s.", direction, port_name, width)
                        else:
                            print(f"{direction} Port found : {port_name} width None")
                            logging.debug("%s Port found : %s width %s.", direction, port_name, width)
                        current_module.ports[direction].append(VerilogPort(port_name, direction, width))


                # Parse declared nets
                net_matches = NET_PATTERN.findall(line)
                for net_group in net_matches:
                    # Split the group by commas to get individual net declarations
                    net_declarations = [decl.strip() for decl in net_group.split(',')]
                    for net_decl in net_declarations:
                        # Check if the net has a width declaration
                        width_match = re.match(r'(\[\d+:\d+\])\s*(\w+)', net_decl)
                        if width_match:
                            width, net_name = width_match.groups()
                            start, end = map(int, re.findall(r'\d+', width))
                            net_obj = VerilogNet(net_name, "wire", (start, end))
                        else:
                            net_name = net_decl
                            net_obj = VerilogNet(net_name, "wire", None)
                        print(f"New net created: {net_name}" + (f" with width {width}" if width_match else ""))
                        logging.info("New net created: %s" + (f" with width {width}" if width_match else ""), net_name)
                        current_module.nets.append(net_obj)

                # Parse instance declarations
                instance_match = INSTANCE_PATTERN.search(line)
                if instance_match:
                    ref_name, instance_name = instance_match.groups()
                    print(f"Instance found : {instance_name}")
                    logging.info("Instance found : %s", instance_name)
                    cell_type = determine_cell_type(ref_name, modules_templates)

                    instance = VerilogInstance(instance_name, cell_type , ref_name)
                    current_module.instances.append(instance)
                    inside_instance = True

                # If inside an instance declaration, match pins
                if inside_instance:
                    print(f"Inside instance: {instance_name}")
                    logging.info("Inside instance: %s", instance_name)
                    pin_matches = PIN_PATTERN.findall(line)
                    # Inside instance, after matching pins
                    for pin_match in pin_matches:
                        pin_name, net_name_instance = pin_match
                        print(f"pin found : {pin_name}")
                        logging.info("pin found : %s", pin_name)
                        print(f"net found : {net_name_instance.strip()}")
                        logging.info("net found : %s", net_name_instance.strip())
                        # Remove any surrounding whitespace and parentheses
                        net_name_instance = net_name_instance.strip()

                        net_obj = None

                        # Handle bit-indexed nets and constants
                        # Could also contain port-derived nets
                        if net_name_instance.endswith(']'):
                            # Extract the base net name and index for bit-indexed nets
                            base_net_name, index = re.match(r"(\w+)\[(\d+)\]", net_name_instance).groups()
                            print(f"Extracted net name, index : {base_net_name} , {index}")
                            logging.info("Extracted net name, index : %s , %s", base_net_name, index)

                            # Check if the base net name is already a declared and a parsed net
                            net_obj = next((net for net in current_module.nets if net.net_type == 'wire' and net.name == base_net_name), None)
                            
                            # Already declared and parsed net
                            if net_obj:
                                print(f"Already declared and parsed net : {base_net_name}")
                                logging.info("Already declared and parsed net : %s", base_net_name)
                                # This condition is added because some nets have the same name as Ports, 
                                # But they are not port-derived nets, they are explicitly declared nets connected to ports.
                                # For such nets we need to add them to the ports they are connected to
                                # There could be a case mismatch. Comparing by ignoring case
                                port_obj = next((port for port in current_module.ports['input'] + current_module.ports['output'] if port.name.lower() == base_net_name.lower()), None)
                                if port_obj is None:
                                    print(f'No matching port found for declared net {net_name_instance} \nContinue creating pin {pin_name}')
                                    logging.info("No matching port found for declared net %s \nContinue creating pin %s", net_name_instance, pin_name)
                                    net_obj = VerilogNet(f"{net_name_instance}", "wire-single", (1,0))
                                    print(f'Created a VerilogNet object for {net_name_instance}')
                                    logging.info("Created a VerilogNet object for %s", net_name_instance)
                                else:
                                    print(f'Found a port name matching a wire net, connecting and adding the net {net_name_instance} to the port {port_obj}')
                                    logging.info("Found a port name matching a wire net, connecting and adding the net %s to the port %s", net_name_instance, port_obj)
                                    net_obj = VerilogNet(f"{net_name_instance}", "wire-single", (1,0))
                                    print(f'Created a VerilogNet object for {net_name_instance}')
                                    logging.info("Created a VerilogNet object for %s", net_name_instance)
                                    port_obj.net.append(net_obj)
                                    print(f'Added the net object to the module ports')
                                    logging.info("Added the net object to the module ports")
                            else:
                                print(f"Not a declared or parsed net")
                                logging.info("Not a declared or parsed net")
                        elif "'" in net_name_instance:
                            print(f'Net name with a constant found {net_name_instance}')
                            logging.info("Net name with a constant found %s", net_name_instance)
                            # Handle constants like 1'b0
                            print(f"Pin {pin_name} connected to a constant {net_name_instance}")
                            logging.info("Pin %s connected to a constant %s", pin_name, net_name_instance)
                            net_obj = VerilogNet(f"{net_name_instance}", "constant", None)
                            print(f'Created a VerilogNet object for {net_name_instance}')
                            logging.info("Created a VerilogNet object for %s", net_name_instance)
                        else:
                            # Check if the net name is one of the module's ports
                            if net_name_instance in [port.name for port in current_module.ports['input'] + current_module.ports['output']]:
                                # It's a port-derived net
                                print('It is a port-derived net')
                                logging.info("It is a port-derived net")
                                port_obj = next((port for port in current_module.ports['input'] + current_module.ports['output'] if port.name == net_name_instance), None)
                                if port_obj:
                                    net_obj = VerilogNet(net_name_instance, "port-derived", (1,0))
                                    print(f'Created a VerilogNet object : {net_name_instance}')
                                    logging.info("Created a VerilogNet object : %s", net_name_instance)
                                    current_module.nets.append(net_obj)
                                    print(f'Added the net object to the module.nets')
                                    logging.info("Added the net object to the module.nets")
                                    port_obj.net.append(net_obj)
                                    print(f'Added the net object to the module ports')
                                    logging.info("Added the net object to the module ports")
                            else:
                                # Handle regular nets
                                net_obj = next((net for net in current_module.nets if net.name == net_name_instance), None)

                        # If no net object was found, it might be a port-derived net 
                        # Port-derived nets
                        if not net_obj:
                            base_net_name = re.match(r"([a-zA-Z_]\w*)\[\d+\]", net_name_instance)
                            if base_net_name:
                                base_net_name = base_net_name.group(1)
                            else:
                                base_net_name = net_name_instance

                            # Check for ports with the same name as the net
                            port_obj = next((port for port in current_module.ports["input"] + current_module.ports["output"] if port.name == base_net_name), None)
                            if port_obj:
                                print('It is a port-derived net')
                                logging.info('It is a port-derived net')
                                print(f"{instance_name} Pin {pin_name} connected to port-derived Net {net_name_instance}")
                                logging.info("%s Pin %s connected to port-derived Net %s", instance_name, pin_name, net_name_instance)
                                net_obj = VerilogNet(net_name_instance, "port-derived", (1,0))
                                print(f"New port-derived Net {net_name_instance} created")
                                logging.info("New port-derived Net %s created", net_name_instance)
                                current_module.nets.append(net_obj)
                                print(f'Port-derived Net {net_name_instance} added to current module.nets')
                                logging.info("Port-derived Net %s added to current module.nets", net_name_instance)
                                port_obj.net.append(net_obj)  # Link the port to its derived net
                                print(f' Net {net_name_instance} added to port_obj')
                                logging.info("Net %s added to port_obj", net_name_instance)
                            else:
                                print(f"No net found for {instance_name} Pin {pin_name} connected to {net_name_instance}")
                                logging.info("No net found for %s Pin %s connected to %s", instance_name, pin_name, net_name_instance)

                        pin = VerilogPin(pin_name, instance, net_obj)
                        instance.pins.append(pin)
                    
                    # Check if this is the end of the instance declaration
                    if ');' in line:
                        inside_instance = False

            # Check for end of module
            if 'endmodule' in line:
                logging.info("End of module: %s", current_module.name)
                print(f"End of module: {current_module.name}")
                current_module = None

        return modules
    
    except Exception as e:
        error_message = f"Error parsing netlist file: {e}"
        logging.error(error_message)
        print(error_message)
        raise ValueError(error_message)

def generate_verilog(modules):
    verilog_code = ""
    for module in modules:
        # Module declaration
        verilog_code += f"module {module.name} (\n"
        for direction in module.ports:
            for port in module.ports[direction]:
                port_width = f"[{port.width[0]}:{port.width[1]}]" if port.width else ""
                verilog_code += f"    {direction} {port_width} {port.name},\n"
        verilog_code = verilog_code.rstrip(',\n') + "\n);\n\n"

        # Wire declarations
        for net in module.nets:
            if net.net_type == "wire":
                net_width = f"[{net.width[0]}:{net.width[1]}]" if net.width else ""
                verilog_code += f"    wire {net_width} {net.name};\n"

        # Instance declarations
        for instance in module.instances:
            verilog_code += f"    {instance.ref_name} {instance.name} ("
            pin_connections = []
            for pin in instance.pins:
                net_name = pin.net.name if pin.net else ""
                # Directly use the net name, as it now includes any indexing
                pin_connections.append(f".{pin.name}({net_name})")
            verilog_code += ", ".join(pin_connections) + ");\n"

        verilog_code += "endmodule\n\n"

    return verilog_code

def verify_parser(modules):
    """
    Verifies and prints the parsed data from a list of VerilogModule objects.

    This function iterates through each VerilogModule object in the provided list,
    printing out details of the module, its ports, nets, and instances. For each
    instance, it also prints the details of its pins and their connections. This
    function is useful for verifying the correctness of the parsed data from a
    Verilog netlist file.

    Args:
        modules (List[VerilogModule]): A list of VerilogModule objects to be verified.

    Returns:
        None: This function does not return anything. It prints the verification details.

    Raises:
        TypeError: If the input is not a list of VerilogModule objects.
        ValueError: If any module, port, net, or instance is malformed.
    """
    # Function Implementation
    
    print('\ndef verify_parser: is called.\n')
    logging.info("verify_parser is called.")
    
    if not isinstance(modules, list):
        logging.error("Expected a list of VerilogModule objects, got %s", type(modules).__name__)
        raise TypeError("Expected a list of VerilogModule objects.")

    for module in modules:
        if not isinstance(module, VerilogModule):
            logging.error("Expected a VerilogModule object, got %s", type(module).__name__)
            raise ValueError("Expected a VerilogModule object.")

        print(f"<----Verifying parser---->")
        logging.info("<----Verifying parser---->")
        print(f"Module: {module.name}")
        logging.info("Module: %s", module.name)

        for direction, ports in module.ports.items():
            for port in ports:
                if not isinstance(port, VerilogPort):
                    logging.error("Expected a VerilogPort object, got %s", type(port).__name__)
                    raise ValueError("Expected a VerilogPort object.")
                print(f"  Port: {port.name}, Direction: {port.direction}, Width: {port.width} ")
                logging.info("  Port: %s, Direction: %s, Width: %s", port.name, port.direction, port.width)
                for net in port.net:
                    print(f"Port-Net : {net}")
                    logging.info("Port-Net : %s", net)

        for net in module.nets:
            if not isinstance(net, VerilogNet):
                logging.error("Expected a VerilogNet object, got %s", type(net).__name__)
                raise ValueError("Expected a VerilogNet object.")
            print(f"  Net: {net.name}, Type: {net.net_type}, Width: {net.width}")
            logging.info("  Net: %s, Type: %s, Width: %s", net.name, net.net_type, net.width)

        for instance in module.instances:
            if not isinstance(instance, VerilogInstance):
                logging.error("Expected a VerilogInstance object, got %s", type(instance).__name__)
                raise ValueError("Expected a VerilogInstance object.")
            print(f"  Instance: {instance.name}, Ref : {instance.ref_name}, Cell Type: {instance.cell_type}")
            logging.info("  Instance: %s, Ref : %s, Cell Type: %s", instance.name, instance.ref_name, instance.cell_type)

            for pin in instance.pins:
                connected_net = pin.net.name if pin.net else "None"
                print(f"    Pin: {pin.name}, Connected to: {connected_net}")
                logging.info("    Pin: %s, Connected to: %s", pin.name, connected_net)

def prepare_graph(modules):
    """
    Prepares data from modules for graph construction.

    Args:
        modules (List[VerilogModule]): A list of VerilogModule objects.

    Returns:
        List[Dict]: A list of dictionaries, each representing a module with its elements (ports, instances, nets)
                    and their connections.
    """
    graph_data = {'nodes': [], 'edges': []}

    for module in modules:
        # Add ports, instances, and nets as nodes
        for direction, ports in module.ports.items():
            for port in ports:
                port_id = f"{module.name}.{port.name}"
                graph_data['nodes'].append({'id': port_id, 'type': 'port', 'direction': direction})

        for instance in module.instances:
            instance_id = f"{module.name}.{instance.name}"
            graph_data['nodes'].append({'id': instance_id, 'type': 'instance'})

            for pin in instance.pins:
                pin_id = f"{instance_id}.{pin.name}"
                graph_data['nodes'].append({'id': pin_id, 'type': 'pin'})
                # Add edge from instance to pin
                graph_data['edges'].append({'from': instance_id, 'to': pin_id})

                if pin.net:
                    net_id = f"{module.name}.{pin.net.name}"
                    # Add edge from pin to net
                    graph_data['edges'].append({'from': pin_id, 'to': net_id})

        # for net in module.nets:
        #     net_id = f"{module.name}.{net.name}"
        #     graph_data['nodes'].append({'id': net_id, 'type': 'net'})

    return graph_data

def load_from_json(file_name):
    with open(file_name, 'r') as file:
        data = json.load(file)
    
    modules = []
    for module_data in data:
        module = VerilogModule(module_data["module_name"])

        # Load ports
        for direction, ports in module_data["ports"].items():
            for port_data in ports:
                width = tuple(port_data["width"]) if port_data["width"] else None
                port = VerilogPort(port_data["name"], port_data["direction"], width)
                module.ports[direction].append(port)

        # Load nets
        net_dict = {}
        for net_data in module_data["nets"]:
            width = tuple(net_data["width"]) if net_data["width"] else None
            net = VerilogNet(net_data["name"], net_data["net_type"], width)
            module.nets.append(net)
            net_dict[net_data["name"]] = net

        # Load instances and pins
        for instance_data in module_data["instances"]:
            instance = VerilogInstance(instance_data["instance"], instance_data["cell_type"], instance_data["ref_name"])
            for pin_data in instance_data["pins"]:
                net_name = pin_data["net"]
                net = None

                # Handle constants
                if "'" in net_name:
                    net = VerilogNet(net_name, "constant", None)
                # Handle indexed nets as 'wire-sub'
                elif '[' in net_name:
                    net = VerilogNet(net_name, "wire-sub", None)
                # Handle regular nets
                else:
                    net = net_dict.get(net_name, None)

                if net is None:
                    print(f"Warning: Net '{net_name}' not found for pin '{pin_data['name']}' in instance '{instance.name}'.")

                pin = VerilogPin(pin_data["name"], instance, net, pin_data.get("direction"))
                instance.pins.append(pin)
            module.instances.append(instance)

        modules.append(module)
    
    return modules

def save_to_json_file(modules, file_name="parsed_objects.json"):
    modules_data = [module.to_dict() for module in modules]
    with open(file_name, 'w') as file:
        json.dump(modules_data, file, indent=4)

def print_module_details(module):
    print(f"Module: {module.name}")
    print("  Ports:")
    for direction, ports in module.ports.items():
        for port in ports:
            print(f"    {direction} - {port.name}, Width: {port.width}, Net: {port.net if port.net else ''}")

    print("  Instances:")
    for instance in module.instances:
        print(f"    Instance: {instance.name}, Cell Type: {instance.cell_type}, Reference: {instance.ref_name}")
        for pin in instance.pins:
            print(f"      Pin: {pin.name}, Net: {pin.net.name if pin.net else 'None'}")

    print("  Nets:")
    for net in module.nets:
        print(f"    Net: {net.name}, Type: {net.net_type}, Width: {net.width}")

def pickling_file(input_file_path, pickled_file_path='pickled_data.pkl', unpickled_file_path='unpickled_data.txt'):
    # Read the content of the input file line by line
    with open(input_file_path, 'r') as input_file:
        file_lines = input_file.readlines()

    # Pickle all lines and save them to a separate file with the highest protocol
    with open(pickled_file_path, 'wb+') as pickle_file:
        pickle.dump(file_lines, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

    # Print a message indicating that pickling is completed
    print(f"Pickling completed. Pickled data saved to: {pickled_file_path}")

    # Unpickle all lines from the pickled file
    with open(pickled_file_path, 'rb+') as pickle_file:
        unpickled_data = pickle.load(pickle_file)

    # # Display the unpickled data
    # print("Unpickled Data:")
    # for line in unpickled_data:
    #     print(line.strip())

    # Save the unpickled data to a separate file
    with open(unpickled_file_path, 'w') as unpickled_file:
        unpickled_file.writelines(unpickled_data)

    print(f"Unpickled data saved to: {unpickled_file_path}")

# Define the retrieve_all_modules function
def retrieve_all_modules(modules):
    with open('query_output_retrieve_all_modules.txt', 'w') as file:
        for module in modules:
            output = f"Module Name: {module.name}\n"
            print(output, end='')
            file.write(output)

# Similarly, modify other functions in the same way
        
def retrieve_ports_and_their_nets_with_port_derived_nets(modules):
    module_name = input("Enter the name of the module to retrieve ports and their nets: ")
    module = next((mod for mod in modules if mod.name == module_name), None)

    if module:
        print(f"Module: {module.name}")
        for direction, ports in module.ports.items():
            print(f"  Relationships for {direction} Port:")
            for port in ports:
                print(f"    Port: {port.name}")
                if port.net:
                    if isinstance(port.net, list):
                        print(f"    Connected Nets:")
                        for connected_net in port.net:
                            print(f"      Net: {connected_net.name}")
                    else:
                        print(f"    Connected Net: {port.net.name}")
                else:
                    print("    No connected nets.")
    else:
        print(f"Error: Module '{module_name}' not found.")

def retrieve_ports_and_their_nets_with_relationships_and_port_derived_nets(modules):
    module_name = input("Enter the name of the module to retrieve ports and their nets: ")
    module = next((mod for mod in modules if mod.name == module_name), None)

    with open('query_output_retrieve_ports_and_their_nets_with_relationships_and_port_derived_nets.txt', 'w') as file:
        if module:
            output = f"Module: {module.name}\n"
            file.write(output)
            print(output, end='')

            for direction, ports in module.ports.items():
                output = f"  Relationships for {direction} Port:\n"
                file.write(output)
                print(output, end='')

                for port in ports:
                    output = f"    Port: {port.name}\n"
                    file.write(output)
                    print(output, end='')

                    if port.net:
                        if isinstance(port.net, list):
                            output = f"    Connected Nets:\n"
                            file.write(output)
                            print(output, end='')

                            for connected_net in port.net:
                                output = f"      Net: {connected_net.name}\n"
                                file.write(output)
                                print(output, end='')
                        else:
                            output = f"    Connected Net: {port.net.name}\n"
                            file.write(output)
                            print(output, end='')
                    else:
                        output = "    No connected nets.\n"
                        file.write(output)
                        print(output, end='')
        else:
            output = f"Error: Module '{module_name}' not found.\n"
            file.write(output)
            print(output, end='')

def retrieve_modules_and_their_ports(modules):
    with open('query_retrieve_modules_and_their_ports','w') as file:
        for module in modules:
            output = f"\nModule: {module.name}"
            file.write(output)
            print(output)

            # Print Relationships
            f"\n  Ports:"
            for port_type, ports in module.ports.items():
                for port in ports:
                    print(f"    {port_type} Port: {port.name}")
                    # for net in port.net:
                    #     print(f"      Connected to Net: {net.name}")

def retrieve_modules_and_their_instances_with_pins(modules):
    for module in modules:
        print(f"\nModule: {module.name}")

        # Print Relationships
        print("  Instances:")
        for instance in module.instances:
            print(f"    Instance: {instance.name}")
            for pin in instance.pins:
                print(f"      Pin: {pin.name} (Connected to Net: {pin.net.name})")

def retrieve_modules_and_their_ports_and_nets(modules):
    for module in modules:
        print(f"\nModule: {module.name}")
        
        # Print Ports
        print("  Ports:")
        for port_direction, ports in module.ports.items():
            for port in ports:
                print(f"    {port_direction} Port: {port.name}")
        
        # Print Nets
        print("  Nets:")
        for net in module.nets:
            print(f"    Net: {net.name} ({net.net_type})")
        
        # # Print Relationships
        # print("  Instances and Pins:")
        # for instance in module.instances:
        #     print(f"    Instance: {instance.name}")
        #     for pin in instance.pins:
        #         print(f"      Pin: {pin.name} (Connected to Net: {pin.net.name})")

def retrieve_ports_and_their_connected_nets(modules):
    for module in modules:
        print(f"\nModule: {module.name}")
        for port_direction, ports in module.ports.items():
            for port in ports:
                print(f"  Port ({port_direction}): {port.name}")
                for net in port.net:
                    net_type = net.net_type
                    net_name = net.name
                    print(f"    Connected Net ({net_type}): {net_name}")

def retrieve_instances_and_their_connected_nets(modules):
    for module in modules:
        print(f"\nModule: {module.name}")
        for instance in module.instances:
            print(f"  Instance: {instance.name}")
            for pin in instance.pins:
                print(f"    Pin: {pin.name}")
                if pin.net:
                    net_type = pin.net.net_type
                    net_name = pin.net.name
                    print(f"      Connected Net ({net_type}): {net_name}")

# def retrieve_modules_and_their_ports_and_nets(modules):
#     for module in modules:
#         print(f"\nModule: {module.name}")
#         print("  Ports:")
#         for direction, ports in module.ports.items():
#             for port in ports:
#                 print(f"    {direction} {port.name}")
#         print("  Nets:")
#         for net in module.nets:
#             print(f"    {net.name}")

def retrieve_modules_with_specific_net(modules):
    net_name = input("Enter the name of the net to retrieve modules: ").strip()

    found_modules = [module.name for module in modules if any(net.name == net_name for net in module.nets)]
    
    if found_modules:
        print(f"Modules with net '{net_name}':")
        for module_name in found_modules:
            print(f"  {module_name}")
    else:
        print(f"No modules found with net '{net_name}'.")

def retrieve_modules_with_specific_port(modules):
    print("Retrieve Modules with a Specific Port:")

    # Ask the user to enter the port name
    port_name = input("Enter the name of the port to search for: ")

    # List to store module names with the specified port
    modules_with_port = []

    for module in modules:
        # Check if the port exists in the module
        if any(port.name == port_name for port_list in module.ports.values() for port in port_list):
            modules_with_port.append(module.name)

    if modules_with_port:
        print(f"Modules with port '{port_name}':")
        for module_name in modules_with_port:
            print(f"  {module_name}")
    else:
        print(f"No modules found with port '{port_name}'.")
    
# Update the retrieve_nets_connected_to_specific_pin function
def retrieve_nets_connected_to_specific_pin(modules):
    print("Retrieve Nets Connected to a Specific Pin:")

    # Ask the user to choose a module
    module_name = input("Enter the name of the module to retrieve instances: ")

    # Find the module in the list of modules
    module = next((mod for mod in modules if mod.name == module_name), None)

    if module:
        # Ask the user to choose an instance
        instance_name = input(f"Enter the name of the instance in module '{module_name}': ")
        instance = next((inst for inst in module.instances if inst.name == instance_name), None)

        if instance:
            # Ask the user to choose a pin
            pin_name = input(f"Enter the name of the pin in instance '{instance_name}': ")
            pin = next((p for p in instance.pins if p.name == pin_name), None)

            if pin:
                print(f"Nets connected to pin '{pin_name}' in instance '{instance_name}' of module '{module_name}':")
                # Check if pin.net is a single VerilogNet object
                if isinstance(pin.net, VerilogNet):
                    print(f"  {pin.net.name}")
                elif isinstance(pin.net, list):
                    # Iterate over the list of VerilogNet objects
                    for net in pin.net:
                        print(f"  {net.name}")
                else:
                    print("Error: Unexpected format for pin.net.")
            else:
                print(f"Error: Pin '{pin_name}' not found in instance '{instance_name}' of module '{module_name}'.")
        else:
            print(f"Error: Instance '{instance_name}' not found in module '{module_name}'.")
    else:
        print(f"Error: Module '{module_name}' not found.")

def retrieve_instances_and_connected_nets_in_module(modules):
    print("Instances and Connected Nets in Modules:")
    for module in modules:
        print(f"Module: {module.name}")
        for instance in module.instances:
            print(f"  Instance: {instance.name}")
            for pin in instance.pins:
                print(f"    Pin: {pin.name} - Connected Net: {pin.net.name}")

def retrieve_all_nets_in_module(modules):
    print("All Nets in Modules:")
    for module in modules:
        print(f"Module: {module.name}")
        for net in module.nets:
            print(f"  Net: {net.name}")
   
def retrieve_all_pins_in_module(modules):
    print("All Pins in Modules:")
    for module in modules:
        print(f"Module: {module.name}")
        for instance in module.instances:
            print(f"  Instance: {instance.name}")
            for pin in instance.pins:
                print(f"    Pin: {pin.name}")

def retrieve_port_derived_nets_connected_to_port(modules):
    print("Port-Derived Nets Connected to Ports:")
    for module in modules:
        for direction, ports in module.ports.items():
            for port in ports:
                if port.net and port.net[0].net_type == 'port-derived':
                    print(f"  Module: {module.name}, Port: {port.name}, Port-Derived Net: {port.net[0].name}")

def retrieve_ports_in_module(modules):
    print("Ports in all modules:")
    for module in modules:
        print(f"\nModule '{module.name}':")
        for direction, ports in module.ports.items():
            for port in ports:
                print(f"  {direction} {port.name}")

def retrieve_all_nets_connected_to_instance(modules):
    print("All Nets Connected to Instances:")
    
    for module in modules:
        for instance in module.instances:
            print(f"Nets connected to instance '{instance.name}' in module '{module.name}':")
            for pin in instance.pins:
                if pin.net:
                    print(f"  Connected Net: {pin.net.name}")
                else:
                    print("  Not Connected to a Net")
            print()  # Add a newline for better readability between instances

def retrieve_all_instances_in_module(modules):
    for module in modules:
        print(f"Instance names for module '{module.name}':")
        if module.instances:
            for instance in module.instances:
                print(f"  {instance.name}")
        else:
            print("  No instances found.")
        print()  # Add a newline for better readability between modules

def add_new_query(queries_list):
    file_name = input("Enter the file name: ")
    
    if os.path.isfile(file_name):
        with open(file_name, 'r') as file:
            query_content = file.read()
            queries_list.append((file_name, query_content.splitlines()))
            print(f"Query added successfully from file '{file_name}'!")
    else:
        print(f"File '{file_name}' does not exist.")

def view_query(queries_list):
    for i, (file_name, query_content) in enumerate(queries_list, 1):
        print(f"{i}. {file_name}:")
        for j, line in enumerate(query_content, 1):
            print(f"   {j}. {line}")

# Update the execute_query function
def execute_query(queries_list, modules):
    view_query(queries_list)
    choice_file = int(input("Enter the number to choose a file: "))

    if 1 <= choice_file <= len(queries_list):
        _, query_content = queries_list[choice_file - 1]

        print("Options:")
        for i, line in enumerate(query_content, 1):
            print(f"   {i}. {line}")

        choice_line = int(input("Enter the line number to execute query: "))

        if 1 <= choice_line <= len(query_content):
            selected_option = query_content[choice_line - 1]

            if selected_option == "Retrieve All Modules:":
                retrieve_all_modules(modules)
            elif selected_option == "Retrieve All Instances in a Module:":
                retrieve_all_instances_in_module(modules)
            elif selected_option == "Retrieve All Nets Connected to an Instance:":
                retrieve_all_nets_connected_to_instance(modules)
            elif selected_option == "Retrieve Ports in a Module:":
                retrieve_ports_in_module(modules)
            elif selected_option == "Retrieve Port-Derived Nets Connected to a Port:":
                retrieve_port_derived_nets_connected_to_port(modules)
            elif selected_option == "Retrieve All Pins in a Module:":
                retrieve_all_pins_in_module(modules)
            elif selected_option == "Retrieve All Nets in a Module:":
                retrieve_all_nets_in_module(modules)
            elif selected_option == "Retrieve Instances and Their Connected Nets in a Module:":
                retrieve_instances_and_connected_nets_in_module(modules)
            elif selected_option == "Retrieve Nets Connected to a Specific Pin:":
                retrieve_nets_connected_to_specific_pin(modules)
            elif selected_option == "Retrieve Modules with a Specific Port:":
                retrieve_modules_with_specific_port(modules)
            elif selected_option == "Retrieve Modules with a Specific Net:":
                retrieve_modules_with_specific_net(modules)
            elif selected_option == "Retrieve Modules and Their Ports and Nets:":
                retrieve_modules_and_their_ports_and_nets(modules)
            elif selected_option == "Retrieve Instances and Their Connected Nets in a Module":
                retrieve_instances_and_their_connected_nets(modules)
            elif selected_option == "Retrieve Ports and Their Connected Nets in a Module:":
                retrieve_ports_and_their_connected_nets(modules)
            elif selected_option == "Retrieve Modules and Their Nets with Relationships:":
                print('retrieve_modules_and_their_nets_with_relationships(modules) is in-progress. Please wait for further developments')
            elif selected_option == "Retrieve Modules and Their Ports, Nets:":
                print('retrieve_modules_and_their_ports_nets(modules) in progress')
            elif selected_option == "Retrieve Modules and Their Instances with Pins:":
                retrieve_modules_and_their_instances_with_pins(modules)
            elif selected_option == "Retrieve Modules and Their Ports:":
                retrieve_modules_and_their_ports(modules)
            elif selected_option == "Retrieve Ports and Their Connected Nets in a Module with Port-Derived Nets:":
                retrieve_ports_and_their_nets_with_relationships_and_port_derived_nets(modules)
            else:
                print(f"Executing query: {selected_option}")
                # Add your code to execute the selected query here
        else:
            print("Invalid line number!")
    else:
        print("Invalid choice!")

def main(input_netlist_file_path):
    """
    Main function to parse and verify a Verilog netlist file.

    This function orchestrates the parsing of a Verilog netlist file. It first extracts module templates,
    then parses instances, and finally parses the entire netlist into VerilogModule objects. It also
    verifies the parsed data for correctness.

    Args:
        file_path (str): Path to the Verilog netlist file.

    Returns:
        None
    """

    # Function Implementation

    # Start a main loop
    # Present three options
    # # POC READ
        # Selecting this option should trigger POC READ        
        # It should first check if parsed_objects.json exists, if yes, parse it into modules, exit
        # If parsed_objects.json not exists, check if pickled file exists, if yes, unpickle it and call the parser
        # If parsed_objects.json and pickled file don't exist, check if input file exists, call the parser on it, if no input file exists, 
        # Once that is done exit to prev loop
    # # POC WRITE
      # generate the input netlist file using the modules.
      # exit
    # # POC QUERY
      # start execution of POC query.
    # # QUIT


    logging.info('Main function called with file path: %s', input_netlist_file_path)
    print('\nMain function called with file path: %s\n', input_netlist_file_path)

    try:
        # Parse module templates from the netlist
        logging.debug('Parsing module templates from the netlist.')
        modules_templates = parse_netlist_hierarchy_module_template(input_netlist_file_path)

        option = 0
        modules = []
        while True:
            print()
            print('###########################################################')
            print()
            print('######################## EDA POC ##########################')
            print()
            print('###########################################################')
            print()
            print()

            print('Choose from below : ')
            print()
            print('1. POC READ')
            print()
            print('2. POC WRITE')
            print()
            print('3. POC QUERY (Note: This feature will not work if executed before POC READ)')
            print()
            print('4. QUIT')
            print()
            option = int(input('Select option 1, 2, 3 or 4 : '))

            if option == 1:
                print('POC READ')
                
                if os.path.exists('parsed_objects.json'):
                    modules = load_from_json('parsed_objects.json')
                    print()
                    print('Modules were parsed and loaded from json, please proceed to POC WRITE\n')                    
                
                elif not os.path.exists('parsed_objects.json') and os.path.exists('netlist_pickle.pkl'):
                    print('Previous database not found, pickle file found, unpickling and parsing')
                    # Unpickle all lines from the pickled file
                    with open('netlist_pickle.pkl', 'rb+') as pickle_file:
                        unpickled_data = pickle.load(pickle_file)
                        # Save the unpickled data to a separate file
                        with open('netlist_unpickled.v.txt', 'w') as unpickled_file:
                            unpickled_file.writelines(unpickled_data)
                    print('Unpickling completed, Parsing file')
                    modules = parse_netlist('netlist_unpickled.v.txt',modules_templates)
                    print('Generating json')
                    save_to_json_file(modules)
                    print('Modules were parsed from pickled netlist file, JSON generated, please proceed to POC WRITE\n')

                elif not os.path.exists('parsed_objects.json') and not os.path.exists('netlist_pickle.pkl') and os.path.exists(input_netlist_file_path):
                    print('Previous database not found, pickle version not found, proceeding with input netlist file ')
                    modules = parse_netlist(input_netlist_file_path,modules_templates)
                    print()
                    print('Generating json')
                    save_to_json_file(modules)                    
                    print('Modules were parsed from input netlist file, please proceed to POC WRITE\n')
                
                else:
                    print('No appropriate netlist file found. Exiting')
                    break
            elif option == 2:
                print('POC WRITE')
                if modules:
                    # Generate the input file from the parsed objects
                    verilog_code = generate_verilog(modules)
                    with open("output_netlist_file.v", "w") as file:
                        file.write(verilog_code)                
                    print('Recreated input netlist from modules, file generated : output_netlist_file.v')             
                else:
                    print('Modules are not initialized, please run POC READ first\n')
            
            elif option == 3:
                print('3. POC QUERY')
                # Ensure the indentation is correct for the following code
                queries_list = []

                while True:
                    print("\nOptions:")
                    print("1. Query")
                    print("2. Quit")

                    option = input("Choose an option (1/2): ")

                    if option == '1':
                        while True:
                            print("\nSub-options:")
                            print("1. Add new query")
                            print("2. View queries")
                            print("3. Execute query")
                            print("4. Back to main menu")

                            sub_option = input("Choose a sub-option (1/2/3/4): ")

                            if sub_option == '1':
                                add_new_query(queries_list)
                                print('ADD')
                            elif sub_option == '2':
                                view_query(queries_list)
                                print('VIEW')
                            elif sub_option == '3':
                                execute_query(queries_list, modules)
                                print('EXECUTE')
                            elif sub_option == '4':
                                print('EXIT')
                                break
                            else:
                                print("Invalid sub-option! Please try again.")

                    elif option == '2':
                        print("Exiting program. Goodbye!")
                        break
                    else:
                        print("Invalid option! Please try again.")


                # # Call the function to print instance names
                # retrieve_all_instances_in_module(modules)
                # retrieve_ports_in_module(modules)
                # # # Call the execute_query function with the updated retrieve_all_nets_connected_to_instance function
                # execute_query(queries_list, modules)                
            else:
                print('QUIT')
                break
        # logging.debug('Reading the file')
        # with open(input_netlist_file_path, 'r') as f:
        #     netlist_lines = f.readlines()

        # # # Parse and verify instances
        # # logging.debug('Parsing and verifying instances.')
        # # instances = validate_instances(netlist_lines, modules_templates)

        # # # Output the results
        # # logging.debug('Outputting module templates and verified instances.')
        # # for module_template in modules_templates:
        # #     logging.info("Module Template: %s", module_template)
        # #     print(f"Module Template: {module_template}")

        # # print("\nVerified Instances:")
        # # for instance in instances:
        # #     logging.debug("Instance: %s", instance)
        # #     print(f"Instance: {instance}")

        # # Before parsing the input file, check for parsed_objects.json

        # # If parsed_objects.json doesn't exist, check for pickled_file

        # # If pickled file doesn't exist, read input file, parse it into objects, pickle the file

        # # Generate the json for the parsed objects

        # if os.path.exists('parsed_objects.json'):
        #     logging.info('Deserializing parsed_objects.json into modules')
        #     print('Deserializing parsed_objects.json into modules')
        #     loaded_modules = load_from_json("parsed_objects.json")            
        # elif os.path.exists('pickled_data.pkl'):
        #     # unpickle the file
        #     # Unpickle all lines from the pickled file
        #     with open('pickled_data.pkl', 'rb+') as pickle_file:
        #         unpickled_data = pickle.load(pickle_file)
        #     pass
        # elif os.path.exists('netlist_file') and not os.path.exists('parsed_objects.json') and not os.path.exists('pickled_data.pkl'):
        #     # use input file as input to the parser
        #     modules = parse_netlist(input_netlist_file_path)
        #     # modules = parse_netlist('input_netlist_file')
        #     # save_to_json()            

            
        
        # # Parse the netlist into VerilogModule objects
        # logging.debug('Parsing the netlist into VerilogModule objects.')
        # modules = parse_netlist(input_netlist_file_path, modules_templates)

        # # Generate the input file from the parsed objects
        # verilog_code = generate_verilog(modules)
        # with open("output_netlist_file.v", "w") as file:
        #     file.write(verilog_code)

        # # # Verify the parsed data
        # # print()
        # # logging.debug('Verifying the parsed data.')
        # # verify_parser(modules)

        # # # Create graph
        # # print()
        # # logging.debug('Creating graph from modules.')
        # # graphs = prepare_graph(modules=modules)
        # logging.info('Serializing the modules into json')
        # print('Serializing the modules into json')
        # save_to_json_file(modules)        

        # # print()
        # # print('################################')
        # # for module in modules:
        # #     print_module_details(module)
        
        # # print()
        # # print('################################')
        # # for module in loaded_modules:
        # #     print_module_details(module)

        # # Generate the input file from the parsed objects
        # verilog_code_2 = generate_verilog(loaded_modules)
        # with open("output_netlist_file_1.v", "w") as file:
        #     file.write(verilog_code_2)

        # logging.info('Main function completed successfully.')

        # print('Done')

    except FileNotFoundError:
        logging.error("FileNotFoundError: The file '%s' was not found.", input_netlist_file_path)
        print(f"Error: The file '{input_netlist_file_path}' was not found.")
    except Exception as e:
        logging.error("Exception occurred: %s", e)
        print(f"An error occurred: {e}")

# Main Execution starts here
if __name__ == "__main__":
    # Define the file path for the netlist file.
    # This is the path to the Verilog netlist file that will be parsed.
    input_netlist_file_path = "netlist_bhuv.v.txt"

    # Call the main function with the file path.
    # The main function orchestrates the parsing of the netlist file and displays the results.
    main(input_netlist_file_path)