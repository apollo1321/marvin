{ nixpkgs, flake-utils }:
with flake-utils.lib; eachSystem [ system.x86_64-linux system.x86_64-darwin ]
  (system:
  let
    pkgs = nixpkgs.legacyPackages.${system};
    devEnv = import ../../devEnv/cpp.nix { inherit pkgs; extraPackages = with pkgs; [ pkgs.protobuf go ]; };
  in
  {
    packages = {
      ds_cli = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = false;
      });

      ds_cli_private = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = true;
      });
    };
  })
