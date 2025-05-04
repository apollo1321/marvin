{
  description = "Marvin - reproducible clients for educational courses";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    nixpkgs.lib.recursiveUpdate
      (import ./courses/ds { inherit nixpkgs flake-utils; })
      (import ./courses/pcp { inherit nixpkgs flake-utils; });
}
