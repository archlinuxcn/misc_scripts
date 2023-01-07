#![allow(clippy::uninlined_format_args)]

mod timer;
mod util;
mod official;
mod cnrepo;

fn main() {
  let rate = 1.0 / (8.0 * 60.0);
  do_work();
  for dur in timer::Timer::new(rate) {
    if let Err(d) = dur {
      eprintln!("behind {:.3}s.", d.as_secs_f32());
      // don't try to compensate missed work
      continue;
    }
    do_work();
  }
}

fn do_work() {
  if let Err(e) = official::do_work() {
    eprintln!("Error while fetching official mirror stats: {:?}", e);
  }
  if let Err(e) = cnrepo::do_work() {
    eprintln!("Error while fetching archlinuxcn mirror stats: {:?}", e);
  }
}

