import os
import itertools
import argparse
import yaml  

def validate_config(input_file, lammps_types, xyz_elements):
    if len(lammps_types) != len(xyz_elements):
        raise ValueError("Error: The number of IDs in lammps_types does not match xyz_elements.")
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Error: Input file '{input_file}' does not exist.")

def convert_lammpstrj_to_xyz(input_file, output_file, lammps_types, xyz_elements, expected_n_atoms=None):
    validate_config(input_file, lammps_types, xyz_elements)
    
    type_map = {str(l_type): element for l_type, element in zip(lammps_types, xyz_elements)}
    fmt_type_map = {k: f"{v:<3}" for k, v in type_map.items()}
    default_element = "X  "
    
    print(f"Starting conversion with ID reordering from '{input_file}' to '{output_file}'...")
    frame_count = 0
    
    with open(input_file, 'r', buffering=16*1024*1024) as infile, \
         open(output_file, 'w', buffering=16*1024*1024) as outfile:
        
        read_line = infile.readline 
        
        while True:
            line = read_line()
            if not line:
                break
            
            if line.startswith("ITEM: TIMESTEP"):
                timestep = read_line().strip()
                read_line() # Skip ITEM: NUMBER OF ATOMS
                n_atoms = int(read_line().strip())
                
                if expected_n_atoms is not None and n_atoms != expected_n_atoms:
                    print(f"Warning: Frame {timestep} has {n_atoms} atoms (expected {expected_n_atoms}).")
                
                box_header = read_line().split()
                is_triclinic = len(box_header) > 3 and "xy" in box_header
                
                line_x = read_line().split()
                line_y = read_line().split()
                line_z = read_line().split()
                
                xlo_b, xhi_b = float(line_x[0]), float(line_x[1])
                ylo_b, yhi_b = float(line_y[0]), float(line_y[1])
                zlo_b, zhi_b = float(line_z[0]), float(line_z[1])
                
                if is_triclinic:
                    xy, xz, yz = float(line_x[2]), float(line_y[2]), float(line_z[2])
                else:
                    xy = xz = yz = 0.0
                
                xlo = xlo_b - min(0.0, xy, xz, xy + xz)
                xhi = xhi_b - max(0.0, xy, xz, xy + xz)
                ylo = ylo_b - min(0.0, yz)
                yhi = yhi_b - max(0.0, yz)
                zlo, zhi = zlo_b, zhi_b
                
                lx, ly, lz = xhi - xlo, yhi - ylo, zhi - zlo
                
                atoms_header = read_line().split()[2:]
                id_idx, type_idx = atoms_header.index("id"), atoms_header.index("type")
                
                if "x" in atoms_header:
                    x_idx, y_idx, z_idx = atoms_header.index("x"), atoms_header.index("y"), atoms_header.index("z")
                elif "xu" in atoms_header:
                    x_idx, y_idx, z_idx = atoms_header.index("xu"), atoms_header.index("yu"), atoms_header.index("zu")
                elif "xs" in atoms_header:
                    x_idx, y_idx, z_idx = atoms_header.index("xs"), atoms_header.index("ys"), atoms_header.index("zs")
                else:
                    raise KeyError("No valid coordinates (x, y, z) found in the file.")
                
                lattice_str = f"Lattice=\"{lx:.3f} 0.000 0.000 {xy:.3f} {ly:.3f} 0.000 {xz:.3f} {yz:.3f} {lz:.3f}\""
                outfile.write(f"{n_atoms}\n{lattice_str} Properties=species:S:1:pos:R:3 pbc=\"T T T\"\n")
                
                atom_lines = itertools.islice(infile, n_atoms)
                parsed_atoms = [(int(parts[id_idx]), parts) for atom_line in atom_lines if (parts := atom_line.split())]
                parsed_atoms.sort(key=lambda a: a[0])
                
                out_lines = [
                    f"{fmt_type_map.get(parts[type_idx], default_element)} {float(parts[x_idx]):12.6f} {float(parts[y_idx]):12.6f} {float(parts[z_idx]):12.6f}\n"
                    for _, parts in parsed_atoms
                ]
                
                outfile.writelines(out_lines)
                frame_count += 1

    print(f"Conversion completed! Processed {frame_count} frames.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LAMMPSTRJ to XYZ converter for Leyla.")
    parser.add_argument("--config", help="Path to leyla_config.yaml file")
    parser.add_argument("--input", help="Input .lammpstrj file")
    parser.add_argument("--output", help="Output .xyz file")
    parser.add_argument("--types", nargs="+", type=int, help="List of LAMMPS type IDs")
    parser.add_argument("--elements", nargs="+", type=str, help="List of elements")
    parser.add_argument("--expected-atoms", type=int, default=None, help="Expected number of atoms per frame")
    
    args = parser.parse_args()
    
    if args.config:
        with open(args.config, 'r') as f:
            cfg = yaml.safe_load(f)
        
        lammps_types = cfg['system']['lammps_types']
        xyz_elements = cfg['system']['xyz_elements']
        expected_n_atoms = cfg['system'].get('expected_n_atoms')
        input_file = cfg['step_01_conversion']['input_file']
        output_file = cfg['step_01_conversion']['output_file']
    else:
        lammps_types = args.types
        xyz_elements = args.elements
        expected_n_atoms = args.expected_atoms
        input_file = args.input
        output_file = args.output
        
    convert_lammpstrj_to_xyz(
        input_file=input_file,
        output_file=output_file,
        lammps_types=lammps_types,
        xyz_elements=xyz_elements,
        expected_n_atoms=expected_n_atoms
    )