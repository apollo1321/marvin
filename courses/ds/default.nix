{ nixpkgs, flake-utils }:
with flake-utils.lib; eachSystem [ system.x86_64-linux system.x86_64-darwin ]
  (system:
  let
    pkgs = nixpkgs.legacyPackages.${system};
    devEnv = import ../../devEnv/cpp.nix { inherit pkgs; extraPackages = with pkgs; [ pkgs.protobuf go ]; };
  in
  {
    packages = {
      cli_ds = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = false;
      });

      cli_ds_private = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = true;
      });
    };
  })
