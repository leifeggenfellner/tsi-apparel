{
  description = "Apparel CSV development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python315.withPackages (pythonPackages: with pythonPackages; [
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
