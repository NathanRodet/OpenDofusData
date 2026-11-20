//! Statistics of the market graph, computed from its points the way the game shows them.

use odd_core::{Period, Periods, Point};
use time::format_description::well_known::Rfc3339;
use time::{Duration, OffsetDateTime, Time, UtcOffset};

const WEEK_IN_DAYS: i64 = 7;

/// The 24 hour, 7 day and 30 day statistics.
///
/// The 7 days start at midnight UTC, seven days before `now`, and use the daily points.
pub(crate) fn periods(hourly: &[Point], daily: &[Point], now: OffsetDateTime) -> Periods {
    let week_start = (now.to_offset(UtcOffset::UTC) - Duration::days(WEEK_IN_DAYS)).replace_time(Time::MIDNIGHT);
    let week: Vec<&Point> = daily
        .iter()
        .filter(|point| parse(&point.at).is_some_and(|at| at >= week_start))
        .collect();
    Periods {
        h24: period_of(hourly.iter().collect()),
        d7: period_of(week),
        d30: period_of(daily.iter().collect()),
    }
}

/// The timestamp of the latest point, exactly as the game wrote it.
pub(crate) fn last_purchase(hourly: &[Point]) -> Option<String> {
    let latest = hourly
        .iter()
        .filter_map(|point| parse(&point.at).map(|at| (at, point)))
        .max_by_key(|(at, _)| *at);
    latest
        .map(|(_, point)| point.at.clone())
        .or_else(|| hourly.last().map(|point| point.at.clone()))
}

fn parse(at: &str) -> Option<OffsetDateTime> {
    OffsetDateTime::parse(at, &Rfc3339).ok()
}

/// Items sold, weighted median price and weighted mean price.
fn period_of(mut points: Vec<&Point>) -> Period {
    let sold: i64 = points.iter().map(|point| point.quantity).sum();
    if sold <= 0 {
        return Period {
            sold: 0,
            median: 0,
            mean: 0.0,
        };
    }
    let spent: i128 = points
        .iter()
        .map(|point| i128::from(point.price) * i128::from(point.quantity))
        .sum();
    points.sort_by_key(|point| point.price);
    let mut seen = 0i64;
    let median = points
        .iter()
        .find(|point| {
            seen += point.quantity;
            seen * 2 >= sold
        })
        .map_or(0, |point| point.price);
    Period {
        sold,
        median,
        mean: spent as f64 / sold as f64,
    }
}
