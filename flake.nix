{
  description = "Apparel CSV development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python315 = pkgs.python315.override {
        packageOverrides = _: super: {
          # mypyc's tests build with -Werror, which trips on a _POSIX_C_SOURCE
          # redefinition in 3.15's pyconfig.h. Pulled in via pip -> sphinx.
          mypy = super.mypy.overridePythonAttrs (_: { doCheck = false; });
        };
      };
      python = python315.withPackages (pythonPackages: with pythonPackages; [
        pip
        polars
        pytest
      ]);
      # pipx's own tests fail against packaging 26 (specifier formatting only).
      pipx = pkgs.pipx.overridePythonAttrs (_: { doCheck = false; });
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [ python pipx pkgs.ruff ];
      };
    };
}
