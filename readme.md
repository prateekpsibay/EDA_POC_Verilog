# Verilog Netlist Parser

This Python script parses Verilog netlist files, extracts module templates, parses instances, and instatitates class objects. It also, generates the input file from the class objects.

## Usage

1. **POC READ:**
    - Parses the input Verilog netlist file and generates parsed objects.
    - If `parsed_objects.json` exists, the script loads modules from it.
    - If not, it checks for a pickled file (`netlist_pickle.pkl`), unpickles it, and calls the parser.
    - If both files are absent, it parses the input netlist file, generates parsed objects, and saves them.

2. **POC WRITE:**
    - Generates a new Verilog netlist file (`output_netlist_file.v`) from the parsed modules.

3. **POC QUERY:**
    <!-- - Allows the user to execute predefined queries on the parsed data.
    - Queries are stored in a list, and the user can add new queries, view existing ones, and execute them. -->
    - Please note that is under implementation.

4. **QUIT:**
    - Exits the program.

## Setup

1. Clone Repository

To clone this repository, use the following command:

```bash
git clone https://github.com/prateekpsibay/EDA_POC_Verilog.git
```

2. Install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

2. Run the script:

    ```bash
    python parser_netlist.py
    ```

## Additional Notes

- The input netlist file is not part of this repository, include the location of the netlist file in the code.

- The `parsed_objects.json` file contains serialized module data for efficient loading.

- The `netlist_pickle.pkl` file stores pickled netlist data for faster parsing.

## Authors

Boomikha

Nandhika

Prateek 




