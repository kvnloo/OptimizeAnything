//! Test adapter: two tab-separated lists of four-digit UTF-16 hex words per line.
#![forbid(unsafe_code)]
use std::io::{self, BufRead, Write};

fn decode(field: &str) -> Result<Vec<u16>, &'static str> {
    if field.is_empty() {
        return Ok(Vec::new());
    }
    let words: Vec<&str> = field.split(',').collect();
    if words.len() > 4096 {
        return Err("too many UTF-16 units");
    }
    words
        .into_iter()
        .map(|word| {
            if word.len() != 4 || !word.bytes().all(|b| b.is_ascii_hexdigit()) {
                return Err("expected four-digit UTF-16 hex word");
            }
            u16::from_str_radix(word, 16).map_err(|_| "invalid UTF-16 unit")
        })
        .collect()
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let stdin = io::stdin();
    let mut stdout = io::BufWriter::new(io::stdout().lock());
    for line in stdin.lock().lines() {
        let line = line?;
        let (a, b) = line.split_once('\t').ok_or("expected a tab separator")?;
        writeln!(stdout, "{}", oa_leven::leven(&decode(a)?, &decode(b)?))?;
    }
    stdout.flush()?;
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
