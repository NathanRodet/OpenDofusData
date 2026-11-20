//! Plain `major.minor.patch` versions, with an optional leading `v`.

/// A version of the application.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version(u64, u64, u64);

impl Version {
    /// Reads `2.4.1` or `v2.4.1`; pre-releases (`2.5.0-rc1`) and anything else are not versions.
    pub fn parse(text: &str) -> Option<Self> {
        let mut parts = text.trim().trim_start_matches('v').split('.');
        let version = Self(
            parts.next()?.parse().ok()?,
            parts.next()?.parse().ok()?,
            parts.next()?.parse().ok()?,
        );
        parts.next().is_none().then_some(version)
    }
}

#[cfg(test)]
mod tests {
    use super::Version;

    #[test]
    fn versions_are_compared_by_number_not_by_text() {
        assert!(Version::parse("v2.10.0") > Version::parse("2.9.9"));
        assert!(Version::parse("2.4.1") > Version::parse("2.4.0"));
        assert_eq!(Version::parse("v2.4.0"), Version::parse("2.4.0"));
    }

    #[test]
    fn anything_else_is_not_a_version() {
        for text in ["", "2.4", "2.4.0.1", "2.5.0-rc1", "latest", "2.x.0"] {
            assert_eq!(Version::parse(text), None, "{text}");
        }
    }
}
