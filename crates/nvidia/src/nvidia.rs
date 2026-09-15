use anyhow::Result;
use futures::AsyncReadExt as _;
use http_client::{
    AsyncBody, CustomHeaders, HttpClient, HttpRequestExt, Method, Request as HttpRequest,
    RequestBuilderExt,
};
use serde::{Deserialize, Serialize};

pub const NVIDIA_API_URL: &str = "https://integrate.api.nvidia.com/v1";

/// NVIDIA NIM's `/v1/models` returns an id per model and nothing else: no
/// context length, no tool or vision support. Every capability below is
/// therefore either this default or an override the user wrote in settings.
/// Erring low is deliberate; a model that silently truncates is worse than one
/// the user has to raise by hand.
pub const DEFAULT_MAX_TOKENS: u64 = 128_000;

#[cfg_attr(feature = "schemars", derive(schemars::JsonSchema))]
#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct Model {
    /// The model's id in the NIM API, e.g. `nvidia/nemotron-3-super-120b-a12b`.
    pub name: String,
    /// The name displayed in the UI, such as in the agent panel model dropdown menu.
    pub display_name: Option<String>,
    pub max_tokens: u64,
    pub max_output_tokens: Option<u64>,
    pub max_completion_tokens: Option<u64>,
    pub supports_tools: Option<bool>,
    pub supports_images: Option<bool>,
    pub parallel_tool_calls: Option<bool>,
}

impl Model {
    /// A model discovered from the API, with no capability metadata attached.
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            display_name: None,
            max_tokens: DEFAULT_MAX_TOKENS,
            max_output_tokens: None,
            max_completion_tokens: None,
            supports_tools: None,
            supports_images: None,
            parallel_tool_calls: None,
        }
    }

    pub fn id(&self) -> &str {
        &self.name
    }

    pub fn display_name(&self) -> &str {
        self.display_name.as_deref().unwrap_or(&self.name)
    }

    pub fn max_token_count(&self) -> u64 {
        self.max_tokens
    }

    pub fn max_output_tokens(&self) -> Option<u64> {
        self.max_output_tokens
    }

    /// NIM serves mostly instruction-tuned models that advertise tool support,
    /// so this defaults on. It is still a guess; the API does not say.
    pub fn supports_tool(&self) -> bool {
        self.supports_tools.unwrap_or(true)
    }

    pub fn supports_images(&self) -> bool {
        self.supports_images.unwrap_or(false)
    }

    /// Defaults OFF, unlike the OpenAI-compatible provider, which forwards
    /// whatever the user declared. zed-industries/zed#55884 reports tool calls
    /// arriving as literal `<tool_call>` text from this endpoint, and sending a
    /// parameter the server does not honour is one of the cheaper explanations
    /// to rule out. Opt in per model via `available_models` if it works.
    pub fn supports_parallel_tool_calls(&self) -> bool {
        self.parallel_tool_calls.unwrap_or(false)
    }
}

#[derive(Deserialize)]
struct ModelsResponse {
    data: Vec<ModelEntry>,
}

#[derive(Deserialize)]
struct ModelEntry {
    id: String,
}

/// Lists the model ids the API key can reach, via the OpenAI-compatible
/// `/models` endpoint NIM exposes.
pub async fn list_models(
    client: &dyn HttpClient,
    api_url: &str,
    api_key: Option<&str>,
    extra_headers: &CustomHeaders,
) -> Result<Vec<String>> {
    let uri = format!("{api_url}/models");
    let request = HttpRequest::builder()
        .method(Method::GET)
        .uri(uri)
        .header("Accept", "application/json")
        .when_some(api_key, |builder, api_key| {
            builder.header("Authorization", format!("Bearer {api_key}"))
        })
        .extra_headers(extra_headers)
        .body(AsyncBody::default())?;

    let mut response = client.send(request).await?;

    let mut body = String::new();
    response.body_mut().read_to_string(&mut body).await?;

    anyhow::ensure!(
        response.status().is_success(),
        "Failed to list NVIDIA models: {} {}",
        response.status(),
        body,
    );

    let response: ModelsResponse = serde_json::from_str(&body)?;
    let mut ids: Vec<String> = response.data.into_iter().map(|model| model.id).collect();
    ids.sort();
    Ok(ids)
}
