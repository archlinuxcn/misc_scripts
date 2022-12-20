mod timer;
mod work;

fn main() {
  let rate = 1.0 / (8.0 * 60.0);
  work::do_work();
  for dur in timer::Timer::new(rate) {
    if let Err(d) = dur {
      eprintln!("behind {:.3}s.", d.as_secs_f32());
    }
    work::do_work();
  }
}
