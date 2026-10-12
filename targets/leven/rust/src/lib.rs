//! Behavioral port of Sindre Sorhus's leven v4.0.0 (MIT; see ../vendor/LICENSE).
//! Operates on UTF-16 code units, including unpaired surrogates.
#![forbid(unsafe_code)]

/// Unit-cost Levenshtein distance. No Unicode normalization or scalar decoding.
/// O(m*n) worst-case time and O(min(m, n)) extra space.
pub fn leven(a: &[u16], b: &[u16]) -> usize {
    let (mut a, mut b) = if a.len() > b.len() { (b, a) } else { (a, b) };
    // As in the upstream algorithm, matching ends cannot increase distance.
    while !a.is_empty() && a.last() == b.last() {
        a = &a[..a.len() - 1];
        b = &b[..b.len() - 1];
    }
    let prefix = a.iter().zip(b).take_while(|(x, y)| x == y).count();
    a = &a[prefix..];
    b = &b[prefix..];
    if a.is_empty() {
        return b.len();
    }
    let mut row: Vec<usize> = (0..=a.len()).collect();
    for (j, right) in b.iter().enumerate() {
        let mut diagonal = row[0];
        row[0] = j + 1;
        for (i, left) in a.iter().enumerate() {
            let old = row[i + 1];
            row[i + 1] = (old + 1)
                .min(row[i] + 1)
                .min(diagonal + usize::from(left != right));
            diagonal = old;
        }
    }
    row[a.len()]
}

#[cfg(test)]
mod tests {
    use super::leven;

    #[test]
    fn basics() {
        let a: Vec<u16> = "kitten".encode_utf16().collect();
        let b: Vec<u16> = "sitting".encode_utf16().collect();
        assert_eq!(leven(&a, &b), 3);
        assert_eq!(leven(&[], &[]), 0);
        assert_eq!(leven(&[97, 98], &[97]), 1);
        assert_eq!(leven(&[97], &[97, 98]), 1);
    }

    #[test]
    fn utf16_not_unicode_scalars() {
        assert_eq!(leven(&[0xD83D, 0xDE00], &[]), 2);
        assert_eq!(leven(&[0xD800], &[0xDC00]), 1);
        assert_eq!(leven(&[0, 0xFFFF], &[0, 0xFFFF]), 0);
    }

    #[test]
    fn independent_repeated_calls() {
        for _ in 0..4 {
            assert_eq!(leven(&[97; 128], &[98; 128]), 128);
            assert_eq!(leven(&[97], &[97]), 0);
            assert_eq!(leven(&[], &[97]), 1);
        }
    }
}
