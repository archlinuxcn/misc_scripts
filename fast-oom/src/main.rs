use std::thread::sleep;
use std::time::Duration;
use std::io::{BufRead, BufReader};

use eyre::Report;

struct MemoryUsage {
  mem_total: u64,
  mem_avail: u64,
  swap_total: u64,
  swap_free: u64,
}

fn get_memory_usage() -> Result<MemoryUsage, Report> {
  let f = std::fs::File::open("/proc/meminfo")?;
  let r = BufReader::new(f);

  let mut mem_total = 0;
  let mut mem_avail = 0;
  let mut swap_total = 0;
  let mut swap_free = 0;
  for line in r.lines() {
    let line = line?;
    if line.starts_with("MemTotal:") {
      mem_total = line.split_whitespace().nth(1).unwrap().parse()?;
    } else if line.starts_with("MemAvailable:") {
      mem_avail = line.split_whitespace().nth(1).unwrap().parse()?;
    } else if line.starts_with("SwapTotal:") {
      swap_total = line.split_whitespace().nth(1).unwrap().parse()?;
    } else if line.starts_with("SwapFree:") {
      swap_free = line.split_whitespace().nth(1).unwrap().parse()?;
    }
  }

  Ok(MemoryUsage {
    mem_total, mem_avail,
    swap_total, swap_free,
  })
}

fn main() {
  loop {
    let mu = get_memory_usage().expect("get_memory_usage");
    // 90% memory and half swap is in use
    let oom = mu.mem_total > mu.mem_avail * 10 && mu.swap_total > mu.swap_free * 2;
    if oom {
      println!("triggering OOM Killer!");
      let _ = std::fs::write("/proc/sysrq-trigger", b"f\n");
      sleep(Duration::from_secs(10));
    } else {
      sleep(Duration::from_secs(1));
    }
  }
}
