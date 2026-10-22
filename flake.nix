{
  description = "Apparel CSV development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python312.withPackages (pythonPackages: with pythonPackages; [
        polars
        pytest
      ]);
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [ python pkgs.ruff ];
      };
    };
}
