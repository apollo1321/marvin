{ pkgs }:
{
  unallowedDevEnv = pkgs.lib.concatStringsSep "|" [
    ".*SSL.*"
    ".*TEMP.*"
    ".*TMP.*"
    "PWD"
    "OLDPWD"
    "system"
    "out"
    "outputs"
    "pname"
    "NIX_ENFORCE_PURITY"
  ];
}
