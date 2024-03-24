// modified from https://github.com/benfred/py-spy/blob/master/src/timer.rs
// MIT license

use std::time::{Instant, Duration};

use rand_distr::{Exp, Distribution};

pub struct Timer {
    start: Instant,
    desired: Duration,
    exp: Exp<f64>,
}

impl Timer {
    pub fn new(rate: f64) -> Timer {
        let start = Instant::now();
        Timer{start, desired: Duration::from_secs(0), exp: Exp::new(rate).unwrap()}
    }
}

impl Iterator for Timer {
    type Item = Result<Duration, Duration>;

    fn next(&mut self) -> Option<Self::Item> {
        let elapsed = self.start.elapsed();

        // figure out how many nanoseconds should come between the previous and
        // the next sample using an exponential distribution to avoid aliasing
        let nanos = 1_000_000_000.0 * self.exp.sample(&mut rand::thread_rng());

        // since we want to account for the amount of time the sampling takes
        // we keep track of when we should sleep to (rather than just sleeping
        // the amount of time from the previous line).
        self.desired += Duration::from_nanos(nanos as u64);

        if self.desired > elapsed {
            Some(Ok(self.desired - elapsed))
        } else {
            Some(Err(elapsed - self.desired))
        }
    }
}
