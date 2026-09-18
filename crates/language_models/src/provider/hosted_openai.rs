//! Hosted APIs that speak the OpenAI chat-completions protocol and list their
//! own models at `/models`: NVIDIA and Groq.
//!
//! These differ from each other only in endpoint, key and a context-length
//! fallback, so they share one implementation driven by [`HostedProvider`]
//! rather than each carrying a copy of it. Adding another such vendor means
//! adding a `static` config and a settings key, not another provider file.

use anyhow::Result;
use collections::BTreeMap;
use credentials_provider::CredentialsProvider;
use futures::{AsyncReadExt as _, FutureExt, StreamExt, future::BoxFuture};
use gpui::{App, AppContext, AsyncApp, Context, Entity, SharedString, Task};
use http_client::{
    AsyncBody, CustomHeaders, HttpClient, Method, Request as HttpRequest, RequestBuilderExt,
};
use language_model::{
    ApiKeyConfiguration, ApiKeyState, AuthenticateError, EnvVar, IconOrSvg, LanguageModel,
    LanguageModelCompletionError, LanguageModelCompletionEvent, LanguageModelId, LanguageModelName,
    LanguageModelProvider, LanguageModelProviderId, LanguageModelProviderName,
    LanguageModelProviderState, LanguageModelRequest, LanguageModelToolChoice,
    LanguageModelToolSchemaFormat, ProviderSettingsView, RateLimiter,
};
use open_ai::ResponseStreamEvent;
use serde::Deserialize;
pub use settings::HostedProviderAvailableModel as AvailableModel;
use settings::{Settings, SettingsStore};
use std::sync::Arc;
use ui::IconName;

/// A hosted, OpenAI-compatible API that lists its models at `{api_url}/models`.
pub struct HostedProvider {
    pub id: &'static str,
    pub name: &'static str,
    pub default_api_url: &'static str,
    pub api_key_env_var: &'static str,
    pub api_key_url: &'static str,
    /// Used when `/models` does not report a context length for a model.
    pub default_max_tokens: u64,
    pub settings: fn(&App) -> &HostedSettings,
}

// OBSERVED 2026-09-18: GET https://integrate.api.nvidia.com/v1/models returns
// only id, object, created and owned_by per model. No context length, no tool
// or vision flags, so every capability here is a default the user can override
// through `available_models`.
pub static NVIDIA: HostedProvider = HostedProvider {
    id: "nvidia",
    name: "NVIDIA",
    default_api_url: "https://integrate.api.nvidia.com/v1",
    api_key_env_var: "NVIDIA_API_KEY",
    api_key_url: "https://build.nvidia.com/settings/api-keys",
    default_max_tokens: 128_000,
    settings: nvidia_settings,
};

// DOCUMENTED (console.groq.com/docs/api-reference): /models returns
// `context_window` and `active` per model, so Groq models get a real context
// length and inactive ones are dropped.
pub static GROQ: HostedProvider = HostedProvider {
    id: "groq",
    name: "Groq",
    default_api_url: "https://api.groq.com/openai/v1",
    api_key_env_var: "GROQ_API_KEY",
    api_key_url: "https://console.groq.com/keys",
    default_max_tokens: 128_000,
    settings: groq_settings,
};

fn nvidia_settings(cx: &App) -> &HostedSettings {
    &crate::AllLanguageModelSettings::get_global(cx).nvidia
}

fn groq_settings(cx: &App) -> &HostedSettings {
    &crate::AllLanguageModelSettings::get_global(cx).groq
}

#[derive(Default, Clone, Debug, PartialEq)]
pub struct HostedSettings {
    pub api_url: String,
    pub auto_discover: bool,
    pub available_models: Vec<AvailableModel>,
    pub custom_headers: CustomHeaders,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Model {
    /// The model's id in the API, e.g. `moonshotai/kimi-k3`.
    pub name: String,
    pub display_name: Option<String>,
    pub max_tokens: u64,
    pub max_output_tokens: Option<u64>,
    pub max_completion_tokens: Option<u64>,
    pub supports_tools: Option<bool>,
    pub supports_images: Option<bool>,
    pub parallel_tool_calls: Option<bool>,
}

impl Model {
    fn discovered(name: String, max_tokens: u64) -> Self {
        Self {
            name,
            display_name: None,
            max_tokens,
            max_output_tokens: None,
            max_completion_tokens: None,
            supports_tools: None,
            supports_images: None,
            parallel_tool_calls: None,
        }
    }

    fn display_name(&self) -> &str {
        self.display_name.as_deref().unwrap_or(&self.name)
    }

    /// Neither API says which models take tools. Most instruction-tuned models
    /// they serve do, so this defaults on; it is still a guess.
    fn supports_tool(&self) -> bool {
        self.supports_tools.unwrap_or(true)
    }

    fn supports_images(&self) -> bool {
        self.supports_images.unwrap_or(false)
    }

    /// Defaults off, unlike the OpenAI-compatible provider, which forwards
    /// whatever the user declared. zed-industries/zed#55884 reports tool calls
    /// arriving from NVIDIA as literal `<tool_call>` text with this turned on in
    /// the reporter's config. Opt in per model through `available_models`.
    fn supports_parallel_tool_calls(&self) -> bool {
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
    #[serde(default)]
    context_window: Option<u64>,
    #[serde(default)]
    active: Option<bool>,
}

// SIMPLIFICATION: substring match on the model id. Neither API says which
// models are chat models, and an embedding or safety-classifier model in the
// picker produces a request that can only fail. Every entry below matches a
// real non-chat id seen in NVIDIA's list or documented by Groq. Replace with a
// capability field if either API ever adds one; the call site does not change.
const NON_CHAT_MARKERS: &[&str] = &[
    "embed", "rerank", "guard", "safety", "reward", "clip", "parse", "detector", "whisper", "tts",
];

fn looks_like_chat_model(id: &str) -> bool {
    let id = id.to_ascii_lowercase();
    !NON_CHAT_MARKERS.iter().any(|marker| id.contains(marker))
}

/// Parses a `/models` response into chat models, sorted by id.
fn parse_models(body: &str, default_max_tokens: u64) -> Result<Vec<Model>> {
    let response: ModelsResponse = serde_json::from_str(body)?;
    let mut models = response
        .data
        .into_iter()
        .filter(|entry| entry.active != Some(false))
        .filter(|entry| looks_like_chat_model(&entry.id))
        .map(|entry| {
            Model::discovered(entry.id, entry.context_window.unwrap_or(default_max_tokens))
        })
        .collect::<Vec<_>>();
    models.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(models)
}

async fn list_models(
    client: &dyn HttpClient,
    api_url: &str,
    api_key: &str,
    extra_headers: &CustomHeaders,
    default_max_tokens: u64,
) -> Result<Vec<Model>> {
    let request = HttpRequest::builder()
        .method(Method::GET)
        .uri(format!("{api_url}/models"))
        .header("Accept", "application/json")
        .header("Authorization", format!("Bearer {api_key}"))
        .extra_headers(extra_headers)
        .body(AsyncBody::default())?;

    let mut response = client.send(request).await?;
    let mut body = String::new();
    response.body_mut().read_to_string(&mut body).await?;
    anyhow::ensure!(
        response.status().is_success(),
        "failed to list models: {} {}",
        response.status(),
        body,
    );
    parse_models(&body, default_max_tokens)
}

pub struct HostedLanguageModelProvider {
    config: &'static HostedProvider,
    http_client: Arc<dyn HttpClient>,
    state: Entity<State>,
}

pub struct State {
    config: &'static HostedProvider,
    api_key_state: ApiKeyState,
    credentials_provider: Arc<dyn CredentialsProvider>,
    http_client: Arc<dyn HttpClient>,
    fetched_models: Vec<Model>,
    fetch_models_task: Option<Task<Result<()>>>,
}

impl State {
    fn is_authenticated(&self) -> bool {
        self.api_key_state.has_key()
    }

    fn set_api_key(&mut self, api_key: Option<String>, cx: &mut Context<Self>) -> Task<Result<()>> {
        let credentials_provider = self.credentials_provider.clone();
        let api_url = api_url(self.config, cx);
        let task = self.api_key_state.store(
            api_url,
            api_key,
            |this| &mut this.api_key_state,
            credentials_provider,
            cx,
        );
        self.fetched_models.clear();
        cx.spawn(async move |this, cx| {
            task.await?;
            this.update(cx, |this, cx| this.restart_fetch_models_task(cx))
        })
    }

    fn authenticate(&mut self, cx: &mut Context<Self>) -> Task<Result<(), AuthenticateError>> {
        let credentials_provider = self.credentials_provider.clone();
        let api_url = api_url(self.config, cx);
        let task = self.api_key_state.load_if_needed(
            api_url,
            |this| &mut this.api_key_state,
            credentials_provider,
            cx,
        );
        cx.spawn(async move |this, cx| {
            let result = task.await;
            this.update(cx, |this, cx| this.restart_fetch_models_task(cx))
                .ok();
            result
        })
    }

    fn fetch_models(&mut self, cx: &mut Context<Self>) -> Task<Result<()>> {
        let config = self.config;
        let settings = (config.settings)(cx);
        let api_url = api_url(config, cx);
        let Some(api_key) = self.api_key_state.key(&api_url) else {
            self.fetched_models.clear();
            return Task::ready(Ok(()));
        };
        if !settings.auto_discover {
            self.fetched_models.clear();
            return Task::ready(Ok(()));
        }

        let http_client = Arc::clone(&self.http_client);
        let extra_headers = settings.custom_headers.clone();
        cx.spawn(async move |this, cx| {
            let models = list_models(
                http_client.as_ref(),
                &api_url,
                &api_key,
                &extra_headers,
                config.default_max_tokens,
            )
            .await?;
            this.update(cx, |this, cx| {
                this.fetched_models = models;
                cx.notify();
            })
        })
    }

    fn restart_fetch_models_task(&mut self, cx: &mut Context<Self>) {
        let task = self.fetch_models(cx);
        self.fetch_models_task.replace(task);
    }
}

fn api_url(config: &HostedProvider, cx: &App) -> SharedString {
    let api_url = &(config.settings)(cx).api_url;
    if api_url.is_empty() {
        SharedString::new_static(config.default_api_url)
    } else {
        SharedString::new(api_url.as_str())
    }
}

impl HostedLanguageModelProvider {
    pub fn new(
        config: &'static HostedProvider,
        http_client: Arc<dyn HttpClient>,
        credentials_provider: Arc<dyn CredentialsProvider>,
        cx: &mut App,
    ) -> Self {
        let state = cx.new(|cx| {
            cx.observe_global::<SettingsStore>(move |this: &mut State, cx| {
                let credentials_provider = this.credentials_provider.clone();
                let api_url = api_url(config, cx);
                this.api_key_state.handle_url_change(
                    api_url,
                    |this| &mut this.api_key_state,
                    credentials_provider,
                    cx,
                );
                this.restart_fetch_models_task(cx);
                cx.notify();
            })
            .detach();
            State {
                config,
                api_key_state: ApiKeyState::new(
                    api_url(config, cx),
                    EnvVar::new(SharedString::new_static(config.api_key_env_var)),
                ),
                credentials_provider,
                http_client: http_client.clone(),
                fetched_models: Vec::new(),
                fetch_models_task: None,
            }
        });

        Self {
            config,
            http_client,
            state,
        }
    }

    fn create_language_model(&self, model: Model) -> Arc<dyn LanguageModel> {
        Arc::new(HostedLanguageModel {
            config: self.config,
            id: LanguageModelId::from(model.name.clone()),
            model,
            state: self.state.clone(),
            http_client: self.http_client.clone(),
            request_limiter: RateLimiter::new(4),
        })
    }
}

impl LanguageModelProviderState for HostedLanguageModelProvider {
    type ObservableEntity = State;

    fn observable_entity(&self) -> Option<Entity<Self::ObservableEntity>> {
        Some(self.state.clone())
    }
}

impl LanguageModelProvider for HostedLanguageModelProvider {
    fn id(&self) -> LanguageModelProviderId {
        LanguageModelProviderId::new(self.config.id)
    }

    fn name(&self) -> LanguageModelProviderName {
        LanguageModelProviderName::new(self.config.name)
    }

    // No vendor marks ship in assets/icons, and drawing a trademarked logo from
    // memory is not something to do casually. The generic OpenAI-compatible
    // glyph is accurate for both. Swap in real icons with attribution in
    // CREDITS.md when they can be added properly.
    fn icon(&self) -> IconOrSvg {
        IconOrSvg::Icon(IconName::AiOpenAiCompat)
    }

    fn default_model(&self, cx: &App) -> Option<Arc<dyn LanguageModel>> {
        self.provided_models(cx).into_iter().next()
    }

    fn default_fast_model(&self, cx: &App) -> Option<Arc<dyn LanguageModel>> {
        self.default_model(cx)
    }

    fn provided_models(&self, cx: &App) -> Vec<Arc<dyn LanguageModel>> {
        let mut models = BTreeMap::default();
        for model in &self.state.read(cx).fetched_models {
            models.insert(model.name.clone(), model.clone());
        }
        // Settings entries win, so a wrong guess from discovery can always be
        // corrected by hand.
        for model in &(self.config.settings)(cx).available_models {
            models.insert(
                model.name.clone(),
                Model {
                    name: model.name.clone(),
                    display_name: model.display_name.clone(),
                    max_tokens: model.max_tokens,
                    max_output_tokens: model.max_output_tokens,
                    max_completion_tokens: model.max_completion_tokens,
                    supports_tools: model.supports_tools,
                    supports_images: model.supports_images,
                    parallel_tool_calls: model.parallel_tool_calls,
                },
            );
        }
        models
            .into_values()
            .map(|model| self.create_language_model(model))
            .collect()
    }

    fn is_authenticated(&self, cx: &App) -> bool {
        self.state.read(cx).is_authenticated()
    }

    fn authenticate(&self, cx: &mut App) -> Task<Result<(), AuthenticateError>> {
        self.state.update(cx, |state, cx| state.authenticate(cx))
    }

    fn settings_view(&self, cx: &mut App) -> Option<ProviderSettingsView> {
        let state = self.state.read(cx);
        Some(ProviderSettingsView::ApiKey(ApiKeyConfiguration::new(
            state.api_key_state.has_key(),
            state.api_key_state.is_from_env_var(),
            state.api_key_state.env_var_name().clone(),
            self.config.api_key_url.into(),
        )))
    }

    fn set_api_key(&self, api_key: Option<String>, cx: &mut App) -> Task<Result<()>> {
        self.state
            .update(cx, |state, cx| state.set_api_key(api_key, cx))
    }
}

pub struct HostedLanguageModel {
    config: &'static HostedProvider,
    id: LanguageModelId,
    model: Model,
    state: Entity<State>,
    http_client: Arc<dyn HttpClient>,
    request_limiter: RateLimiter,
}

impl HostedLanguageModel {
    fn stream_completion(
        &self,
        request: open_ai::Request,
        cx: &AsyncApp,
    ) -> BoxFuture<
        'static,
        Result<
            futures::stream::BoxStream<'static, Result<ResponseStreamEvent>>,
            LanguageModelCompletionError,
        >,
    > {
        let http_client = self.http_client.clone();
        let config = self.config;
        let (api_key, api_url, extra_headers) = self.state.read_with(cx, |state, cx| {
            let api_url = api_url(config, cx);
            let extra_headers = (config.settings)(cx).custom_headers.clone();
            (state.api_key_state.key(&api_url), api_url, extra_headers)
        });

        let future = self.request_limiter.stream(async move {
            let provider = LanguageModelProviderName::new(config.name);
            let Some(api_key) = api_key else {
                return Err(LanguageModelCompletionError::NoApiKey { provider });
            };
            let request = open_ai::stream_completion(
                http_client.as_ref(),
                provider.0.as_str(),
                &api_url,
                &api_key,
                request,
                &extra_headers,
            );
            Ok(request.await?)
        });

        async move { Ok(future.await?.boxed()) }.boxed()
    }
}

impl LanguageModel for HostedLanguageModel {
    fn id(&self) -> LanguageModelId {
        self.id.clone()
    }

    fn name(&self) -> LanguageModelName {
        LanguageModelName::from(self.model.display_name().to_string())
    }

    fn provider_id(&self) -> LanguageModelProviderId {
        LanguageModelProviderId::new(self.config.id)
    }

    fn provider_name(&self) -> LanguageModelProviderName {
        LanguageModelProviderName::new(self.config.name)
    }

    fn supports_tools(&self) -> bool {
        self.model.supports_tool()
    }

    fn supports_images(&self) -> bool {
        self.model.supports_images()
    }

    fn supports_streaming_tools(&self) -> bool {
        true
    }

    fn supports_tool_choice(&self, choice: LanguageModelToolChoice) -> bool {
        match choice {
            LanguageModelToolChoice::Auto
            | LanguageModelToolChoice::Any
            | LanguageModelToolChoice::None => true,
        }
    }

    fn tool_input_format(&self) -> LanguageModelToolSchemaFormat {
        LanguageModelToolSchemaFormat::JsonSchema
    }

    fn telemetry_id(&self) -> String {
        format!("{}/{}", self.config.id, self.model.name)
    }

    fn max_token_count(&self) -> u64 {
        self.model.max_tokens
    }

    fn max_output_tokens(&self) -> Option<u64> {
        self.model.max_output_tokens
    }

    fn stream_completion(
        &self,
        request: LanguageModelRequest,
        cx: &AsyncApp,
    ) -> BoxFuture<
        'static,
        Result<
            futures::stream::BoxStream<
                'static,
                Result<LanguageModelCompletionEvent, LanguageModelCompletionError>,
            >,
            LanguageModelCompletionError,
        >,
    > {
        let request = match crate::provider::open_ai::into_open_ai(
            request,
            &self.model.name,
            self.model.supports_parallel_tool_calls(),
            false,
            self.max_output_tokens(),
            crate::provider::open_ai::ChatCompletionMaxTokensParameter::MaxTokens,
            None,
            false,
        ) {
            Ok(request) => request,
            Err(error) => return async move { Err(error.into()) }.boxed(),
        };
        let completions = self.stream_completion(request, cx);
        async move {
            let mapper = crate::provider::open_ai::OpenAiEventMapper::new();
            Ok(mapper.map_stream(completions.await?).boxed())
        }
        .boxed()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Trimmed from a real response, 2026-09-18. NVIDIA reports no context
    // length, so the fallback applies.
    const NVIDIA_MODELS: &str = r#"{"object":"list","data":[
        {"id":"moonshotai/kimi-k3","object":"model","created":735790403,"owned_by":"moonshotai"},
        {"id":"nvidia/nv-embedqa-mistral-7b-v2","object":"model","created":735790403,"owned_by":"nvidia"},
        {"id":"meta/llama-guard-4-12b","object":"model","created":735790403,"owned_by":"meta"},
        {"id":"nvidia/nemotron-4-340b-reward","object":"model","created":735790403,"owned_by":"nvidia"},
        {"id":"deepseek-ai/deepseek-v4-flash-0731","object":"model","created":735790403,"owned_by":"deepseek-ai"}
    ]}"#;

    // Shape from Groq's API reference: context_window and active per model.
    const GROQ_MODELS: &str = r#"{"object":"list","data":[
        {"id":"llama-3.3-70b-versatile","object":"model","created":1,"owned_by":"Meta","active":true,"context_window":131072},
        {"id":"whisper-large-v3","object":"model","created":1,"owned_by":"OpenAI","active":true,"context_window":448},
        {"id":"retired-model","object":"model","created":1,"owned_by":"x","active":false,"context_window":8192}
    ]}"#;

    #[test]
    fn nvidia_keeps_chat_models_and_uses_the_fallback_context() {
        let models = parse_models(NVIDIA_MODELS, 128_000).unwrap();
        let ids = models.iter().map(|m| m.name.as_str()).collect::<Vec<_>>();
        assert_eq!(
            ids,
            ["deepseek-ai/deepseek-v4-flash-0731", "moonshotai/kimi-k3"]
        );
        assert!(models.iter().all(|m| m.max_tokens == 128_000));
    }

    #[test]
    fn groq_uses_reported_context_and_drops_inactive_and_speech_models() {
        let models = parse_models(GROQ_MODELS, 128_000).unwrap();
        assert_eq!(models.len(), 1);
        assert_eq!(models[0].name, "llama-3.3-70b-versatile");
        assert_eq!(models[0].max_tokens, 131_072);
    }

    #[test]
    fn parallel_tool_calls_default_off() {
        let model = Model::discovered("any".into(), 1);
        assert!(!model.supports_parallel_tool_calls());
        assert!(model.supports_tool());
    }
}
