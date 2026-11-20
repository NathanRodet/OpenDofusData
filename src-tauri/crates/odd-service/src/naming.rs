//! Putting the names of items and of types of items in the summary of a log line.

use std::collections::HashMap;

/// The names the interface can show, by identifier.
#[derive(Debug, Default)]
pub(crate) struct Names {
    pub(crate) items: HashMap<i64, String>,
    pub(crate) item_types: HashMap<i64, String>,
}

impl Names {
    /// The summary with the item or the type named, when their names are known.
    pub(crate) fn summary(&self, summary: &str, item_id: Option<i64>, item_type_id: Option<i64>) -> String {
        let named = name_the(summary, "l'objet", item_id, &self.items);
        name_the(&named, "le type", item_type_id, &self.item_types)
    }
}

/// Replaces `<label> 123` with `Name (123)` when the name is known; the summary is left alone otherwise.
fn name_the(summary: &str, label: &str, id: Option<i64>, names: &HashMap<i64, String>) -> String {
    let (Some(id), wanted) = (id, format!("{label} {}", id.unwrap_or_default())) else {
        return summary.to_owned();
    };
    let Some(name) = names.get(&id) else {
        return summary.to_owned();
    };
    match summary.find(&wanted) {
        Some(start) if !summary[start + wanted.len()..].starts_with(|c: char| c.is_ascii_digit()) => {
            format!("{}{name} ({id}){}", &summary[..start], &summary[start + wanted.len()..])
        }
        _ => summary.to_owned(),
    }
}

#[cfg(test)]
mod tests {
    use super::Names;

    fn names() -> Names {
        Names {
            items: [(32244, "Dragoeuf".to_owned())].into(),
            item_types: [(6, "Épée".to_owned()), (211, "Familier".to_owned())].into(),
        }
    }

    #[test]
    fn a_known_item_is_named_with_its_identifier() {
        assert_eq!(
            names().summary("17 offres pour l'objet 32244", Some(32244), None),
            "17 offres pour Dragoeuf (32244)"
        );
        assert_eq!(
            names().summary("Brisage de l'objet 32244, coefficient 117 %", Some(32244), None),
            "Brisage de Dragoeuf (32244), coefficient 117 %"
        );
    }

    #[test]
    fn a_known_type_is_named_with_its_identifier() {
        assert_eq!(
            names().summary("95 objets en vente dans le type 6", None, Some(6)),
            "95 objets en vente dans Épée (6)"
        );
    }

    #[test]
    fn an_unknown_name_or_no_identifier_changes_nothing() {
        let text = "17 offres pour l'objet 99";
        assert_eq!(names().summary(text, Some(99), None), text);
        assert_eq!(
            names().summary("2 objets dans le type 77", None, Some(77)),
            "2 objets dans le type 77"
        );
        assert_eq!(names().summary(text, None, None), text);
    }

    #[test]
    fn only_the_identifier_of_the_line_is_replaced() {
        let text = "offres pour l'objet 322441";
        assert_eq!(names().summary(text, Some(32244), None), text);
        let types = "dans le type 66";
        assert_eq!(names().summary(types, None, Some(6)), types);
    }
}
