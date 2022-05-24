# mol-converter
molecule file format converter using openbabel, slurm

### usage
```shell
$ python main.py --help
Usage: main.py [OPTIONS]

Options:
  --src PATH                  input molecule file or directory. ex) source.mol2, ./target  [required]
  --output_format TEXT        output molecule file format. ex) sdf, pdbqt  [required]
  --dist PATH                 output molecule dist directory.  [default: ./dist]
  --babel_cmd [babel|obabel]  babel command.  [default: obabel]
  --babel_option TEXT         open babel options. ex) --gen3d -p 7.4
  --help                      Show this message and exit.

$ python main.py --src test.mol2 --output_format sdf --babel_option "-gen3D -p 7.4" --dist ./dist
```
