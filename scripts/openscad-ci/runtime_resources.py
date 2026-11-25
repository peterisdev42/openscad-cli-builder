"""Share the native/WASM resource layout rules and smoke-model dependency."""
import shutil

BASE_RESOURCES = ("color-schemes", "libraries", "fonts", "examples")


def resource_names(modern=False):
    return BASE_RESOURCES + (("shaders", "templates") if modern else ())


def check_source_resources(source, modern=False):
    for name in resource_names(modern):
        path = source / name
        # RC1 and newer upstream installers create an empty libraries directory.
        # Older supported versions must still ship their original library tree.
        if name == "libraries" and modern and not path.exists():
            continue
        if not path.is_dir():
            raise FileNotFoundError(f"Required OpenSCAD source resource missing: {path}")
    for name in ("CMakeLists.txt", "COPYING", "locale/LINGUAS"):
        if not (source / name).is_file():
            raise FileNotFoundError(f"Required OpenSCAD source file missing: {source / name}")


def copy_runtime_resources(source, resources, modern=False, wasm=False):
    check_source_resources(source, modern)
    for name in (BASE_RESOURCES if wasm else resource_names(modern)):
        path = source / name
        if name == "libraries" and not path.exists():
            (resources / name).mkdir(parents=True, exist_ok=True)
        else:
            shutil.copytree(path, resources / name, dirs_exist_ok=True)


def smoke_library(resources, test):
    # Exercise bundled MCAD when supplied by upstream. For newer versions
    # without MCAD, exercise local use<> resolution with our own tiny fixture.
    if (resources / "libraries/MCAD/boxes.scad").is_file():
        return "MCAD/boxes.scad"
    (test / "smoke-library.scad").write_text(
        "module roundedBox(size, r, sidesonly=false) {\n"
        "  hull() for (x=[-1,1], y=[-1,1])\n"
        "    translate([x*(size[0]/2-r),y*(size[1]/2-r),-size[2]/2])\n"
        "      cylinder(h=size[2],r=r,$fn=24);\n"
        "}\n", encoding="utf-8")
    return "smoke-library.scad"


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--modern", action="store_true")
    args = parser.parse_args()
    check_source_resources(args.source, args.modern)
    print("Source resource layout validated")


if __name__ == "__main__":
    main()
