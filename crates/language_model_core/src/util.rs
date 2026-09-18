use std::str::FromStr;

/// Parses tool call arguments JSON, treating empty strings as empty objects.
///
/// Many LLM providers return empty strings for tool calls with no arguments.
/// This helper normalizes that behavior by converting empty strings to `{}`.
pub fn parse_tool_arguments(arguments: &str) -> Result<serde_json::Value, serde_json::Error> {
    if arguments.is_empty() {
        Ok(serde_json::Value::Object(Default::default()))
    } else {
        serde_json::Value::from_str(arguments)
    }
}

/// `partial_json_fixer::fix_json` converts a trailing `\` inside a string into `\\`
/// (a literal backslash). When used for incremental parsing (comparing successive
/// parses to extract deltas), this produces a spurious backslash character that
/// doesn't exist in the final text, corrupting the output.
///
/// This function strips any trailing incomplete escape sequence before fixing,
/// so each intermediate parse produces a true prefix of the final string value.
pub fn fix_streamed_json(partial_json: &str) -> String {
    let json = strip_trailing_incomplete_escape(partial_json);
    partial_json_fixer::fix_json(json)
}

fn strip_trailing_incomplete_escape(json: &str) -> &str {
    let trailing_backslashes = json
        .as_bytes()
        .iter()
        .rev()
        .take_while(|&&b| b == b'\\')
        .count();
    if trailing_backslashes % 2 == 1 {
        &json[..json.len() - 1]
    } else {
        json
    }
}

/// Parses a "prompt is too long: N tokens ..." message and extracts the token count.
pub fn parse_prompt_too_long(message: &str) -> Option<u64> {
    message
        .strip_prefix("prompt is too long: ")?
        .split_once(" tokens")?
        .0
        .parse()
        .ok()
}

/// Recognizes a request rejected for being larger than the account's per-minute
/// token quota, which is a different problem from the model's context window.
/// Groq's on-demand tier sends these as HTTP 413, naming either "tokens per
/// minute (TPM)" or "input tokens per minute (ITPM)".
pub fn is_per_minute_token_quota_message(message: &str) -> bool {
    message.contains("tokens per minute")
}

/// Extracts the readable text from an OpenAI-style `{"error": {"message": ...}}`
/// body, falling back to the body as it arrived.
pub fn provider_error_message(body: &str) -> String {
    serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .and_then(|value| value["error"]["message"].as_str().map(str::to_owned))
        .unwrap_or_else(|| body.to_owned())
}

/// Recognizes OpenAI-style context window overflow errors, which arrive either
/// with the `context_length_exceeded` error code or a "Your input exceeds the
/// context window of this model" message.
pub fn is_context_window_exceeded_message(message: &str) -> bool {
    message.contains("context_length_exceeded") || message.contains("exceeds the context window")
}

#[cfg(test)]
mod tests {
    use super::*;

    // Verbatim from Groq, 2026-09-18, organization id removed. A "hello" to the
    // agent costs over 11K tokens once the system prompt and tool definitions
    // are included, against an 8K-per-minute free-tier quota.
    const GROQ_TPM_413: &str = r#"{"error":{"message":"Request too large for model `openai/gpt-oss-120b` in organization `org_x` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 11387, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing","type":"tokens","code":"rate_limit_exceeded"}}"#;
    const GROQ_ITPM_413: &str = r#"{"error":{"message":"Request too large for model `qwen/qwen3.8-27b` in organization `org_x` service tier `on_demand` on input tokens per minute (ITPM): Limit 7000, Requested 12630, please reduce your message size and try again.","type":"tokens","code":"rate_limit_exceeded"}}"#;

    #[test]
    fn per_minute_quota_is_not_a_context_window_overflow() {
        for body in [GROQ_TPM_413, GROQ_ITPM_413] {
            assert!(is_per_minute_token_quota_message(body));
            assert!(!is_context_window_exceeded_message(body));
        }
        assert!(!is_per_minute_token_quota_message(
            "prompt is too long: 250000 tokens > 200000 maximum"
        ));
    }

    #[test]
    fn provider_error_message_unwraps_json_and_passes_plain_text_through() {
        assert!(provider_error_message(GROQ_TPM_413).starts_with("Request too large for model"));
        assert_eq!(provider_error_message("plain text"), "plain text");
    }

    #[test]
    fn test_fix_streamed_json_strips_incomplete_escape() {
        let fixed = fix_streamed_json(r#"{"text": "hello\"#);
        let parsed: serde_json::Value = serde_json::from_str(&fixed).expect("valid json");
        assert_eq!(parsed["text"], "hello");
    }

    #[test]
    fn test_fix_streamed_json_preserves_complete_escape() {
        let fixed = fix_streamed_json(r#"{"text": "hello\\"#);
        let parsed: serde_json::Value = serde_json::from_str(&fixed).expect("valid json");
        assert_eq!(parsed["text"], "hello\\");
    }

    #[test]
    fn test_fix_streamed_json_strips_escape_after_complete_escape() {
        let fixed = fix_streamed_json(r#"{"text": "hello\\\"#);
        let parsed: serde_json::Value = serde_json::from_str(&fixed).expect("valid json");
        assert_eq!(parsed["text"], "hello\\");
    }

    #[test]
    fn test_fix_streamed_json_no_escape_at_end() {
        let fixed = fix_streamed_json(r#"{"text": "hello"#);
        let parsed: serde_json::Value = serde_json::from_str(&fixed).expect("valid json");
        assert_eq!(parsed["text"], "hello");
    }

    #[test]
    fn test_fix_streamed_json_newline_escape_boundary() {
        let fixed = fix_streamed_json(r#"{"text": "line1\"#);
        let parsed: serde_json::Value = serde_json::from_str(&fixed).expect("valid json");
        assert_eq!(parsed["text"], "line1");

        let fixed = fix_streamed_json(r#"{"text": "line1\nline2"#);
        let parsed: serde_json::Value = serde_json::from_str(&fixed).expect("valid json");
        assert_eq!(parsed["text"], "line1\nline2");
    }

    #[test]
    fn test_fix_streamed_json_incremental_delta_correctness() {
        let chunk1 = r#"{"replacement_text": "fn foo() {\"#;
        let fixed1 = fix_streamed_json(chunk1);
        let parsed1: serde_json::Value = serde_json::from_str(&fixed1).expect("valid json");
        let text1 = parsed1["replacement_text"].as_str().expect("string");
        assert_eq!(text1, "fn foo() {");

        let chunk2 = r#"{"replacement_text": "fn foo() {\n    return bar;\n}"}"#;
        let fixed2 = fix_streamed_json(chunk2);
        let parsed2: serde_json::Value = serde_json::from_str(&fixed2).expect("valid json");
        let text2 = parsed2["replacement_text"].as_str().expect("string");
        assert_eq!(text2, "fn foo() {\n    return bar;\n}");

        let delta = &text2[text1.len()..];
        assert_eq!(delta, "\n    return bar;\n}");
    }
}
