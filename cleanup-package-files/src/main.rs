use std::process::Command;
use std::path::Path;
use std::ffi::{OsStr, OsString};
use std::os::unix::ffi::OsStrExt;
use std::fs::File;
use std::os::unix::io::IntoRawFd;

use expanduser::expanduser;
use eyre::{Result, ensure, eyre};
use structopt::StructOpt;

const LILAC_LOCK: &str = "~lilydjwg/.lilac/.lock";
const LILAC_REPO: &str = "~lilydjwg/archgitrepo/archlinuxcn";
const USER: &str = "lilydjwg";

fn flock<P: AsRef<Path>>(lockfile: P) -> Result<()> {
  let f = File::open(lockfile.as_ref())?;
  let fd = f.into_raw_fd();
  if nix::fcntl::flock(fd, nix::fcntl::FlockArg::LockExclusiveNonblock).is_err() {
    eprintln!("Waiting for lock file {} to release...", lockfile.as_ref().display());
    nix::fcntl::flock(fd, nix::fcntl::FlockArg::LockExclusive)?;
  }
  Ok(())
}

fn git_ls_files() -> Result<Vec<OsString>> {
  let output = Command::new("git").arg("ls-files").output()?;
  ensure!(output.status.success(),
    "{:?}: {}", output.status, String::from_utf8_lossy(&output.stderr));
  Ok(
    output.stdout.split(|c| *c == b'\n')
      .map(|line| OsStr::from_bytes(line).to_owned())
      .collect()
  )
}

#[derive(StructOpt, Debug)]
#[structopt(name = "basic")]
struct Opt {
  /// remove files for real; or only print what will be removed
  #[structopt(long="real")]
  real: bool,
  pkgname: String,
}

fn main() -> Result<()> {
  let opt = Opt::from_args();

  let pwd = pwd::Passwd::from_name(USER)
    .map_err(|e| eyre!("cannot get passwd entry for user {}: {:?}", USER, e))?
    .unwrap();
  nix::unistd::setuid(nix::unistd::Uid::from_raw(pwd.uid))?;

  if opt.real {
    flock(&expanduser(LILAC_LOCK)?)?;
  }
  let mut path = expanduser(LILAC_REPO)?;
  path.push(&opt.pkgname);

  std::env::set_current_dir(&path)?;
  let tracked_files = git_ls_files()?;

  for entry in path.read_dir()? {
    let entry = entry?;
    let file_name = entry.file_name();
    if tracked_files.contains(&file_name) {
      continue;
    }
    if opt.real {
      println!("rm -rf {}", entry.path().display());
      Command::new("rm").arg("-rf").arg(&file_name).spawn()?;
    } else {
      println!("Would rm -rf {}", entry.path().display());
    }
  }

  Ok(())
}
