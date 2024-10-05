use std::io::IsTerminal;

use tracing_subscriber::EnvFilter;
pub use eyre::Result;

pub fn setup_logging(default_level: &str) -> Result<()> {
  let filter = EnvFilter::try_from_default_env()
    .unwrap_or_else(|_| EnvFilter::from(default_level));
  let isatty = std::io::stderr().is_terminal();
  let fmt = tracing_subscriber::fmt::fmt()
    .with_writer(std::io::stderr)
    .with_env_filter(filter)
    .with_ansi(isatty);
  if isatty {
    fmt
      .with_timer(tracing_subscriber::fmt::time::ChronoLocal::new(
          String::from("%Y-%m-%d %H:%M:%S%.6f %z")))
      .init();
  } else {
    fmt.without_time().init();
  }

  Ok(())
}

