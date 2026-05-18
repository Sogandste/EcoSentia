```python
"""
EcoSentia Evaluation Platform - Integrated Application
A Streamlit-based interface for scientific claim evaluation with evidence scanning.
"""

import streamlit as st
import requests
import httpx
import asyncio
import logging
import hashlib
import json
import yaml
from typing import Dict, Any, Optional, Callable, Tuple, List, Literal
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, validator, ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Settings:
    """Application configuration settings."""
    api_url: str = "https://ecosentia.onrender.com"
    timeout: int = 120
    log_level: str = "INFO"
    cache_ttl: int = 3600
    max_retries: int = 3
    max_history_entries: int = 50
    
    @classmethod
    def load_from_yaml(cls, profile: str = "production") -> "Settings":
        """Load configuration from YAML file based on profile."""
        config_path = Path("config.yaml")
        if not config_path.exists():
            return cls()
        
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            if "profiles" not in config or profile not in config["profiles"]:
                return cls()
            
            profile_config = config["profiles"][profile]
            return cls(**profile_config)
        except Exception as exc:
            logging.error(f"Failed to load config: {exc}")
            return cls()

# Initialize settings
settings = Settings()

# ============================================================================
# LOGGING SETUP
# ============================================================================

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f'ecosentia_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

class EvaluationRequest(BaseModel):
    """Validated input model for evaluation requests."""
    claim: str = Field(..., min_length=10, max_length=1000)
    preset: Literal["Fog", "EV", "Custom"]
    lens: Literal["mechanism", "context", "scale", "manufacturability", "safety"]
    source: Literal["Both", "PubMed", "OpenAlex"] = "Both"
    max_results: int = Field(5, ge=1, le=10)
    
    @validator("claim")
    def claim_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Claim cannot be empty")
        return v.strip()
    
    class Config:
        frozen = True

@dataclass
class EvaluationHistory:
    """Record of a single evaluation for history tracking."""
    timestamp: datetime
    claim: str
    preset: str
    lens: str
    support_level: str
    snapshot: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class PanelState:
    """State container for a single evaluation panel."""
    refined_query: Optional[str] = None
    scan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    is_processing: bool = False
    last_updated: Optional[datetime] = None
    
    def reset(self):
        """Reset panel state to initial values."""
        self.refined_query = None
        self.scan = None
        self.error = None
        self.is_processing = False
        self.last_updated = None

# ============================================================================
# API CLIENT
# ============================================================================

class EcoSentiaAPI:
    """
    API client for EcoSentia evidence evaluation service.
    Supports both sync and async operations with retry logic.
    """
    
    def __init__(
        self,
        base_url: str = settings.api_url,
        timeout: int = settings.timeout
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self._async_client: Optional[httpx.AsyncClient] = None
        
    @property
    def async_client(self) -> httpx.AsyncClient:
        """Lazy initialization of async client."""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._async_client
    
    async def close_async_client(self):
        """Properly close async client."""
        if self._async_client is not None and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None
    
    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
        reraise=True
    )
    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute POST request with automatic retry on network errors.
        Does not retry on 4xx client errors.
        """
        request_id = self._generate_request_id(payload)
        url = f"{self.base_url}{path}"
        logger.info(f"[{request_id}] POST {url}")
        
        try:
            resp = self.session.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            
            logger.info(
                f"[{request_id}] Response {resp.status_code} "
                f"in {resp.elapsed.total_seconds():.2f}s"
            )
            
            # Don't retry on client errors
            if 400 <= resp.status_code < 500:
                error_detail = self._extract_error_message(resp)
                logger.error(f"[{request_id}] Client error: {error_detail}")
                raise ValueError(f"API client error: {error_detail}")
            
            resp.raise_for_status()
            
            # Validate response is JSON
            try:
                return resp.json()
            except json.JSONDecodeError:
                logger.error(f"[{request_id}] Invalid JSON response")
                raise ValueError("API returned invalid JSON")
            
        except requests.Timeout:
            logger.error(f"[{request_id}] Request timeout after {self.timeout}s")
            raise TimeoutError(f"Request timeout after {self.timeout}s")
            
        except requests.RequestException as exc:
            logger.error(
                f"[{request_id}] Request failed: {exc}",
                exc_info=True
            )
            raise
    
    async def _async_post(
        self,
        path: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Async POST request with error handling."""
        request_id = self._generate_request_id(payload)
        url = f"{self.base_url}{path}"
        logger.info(f"[{request_id}] Async POST {url}")
        
        try:
            resp = await self.async_client.post(url, json=payload)
            
            logger.info(f"[{request_id}] Async response {resp.status_code}")
            
            # Handle client errors
            if 400 <= resp.status_code < 500:
                error_detail = self._extract_error_message_async(resp)
                logger.error(f"[{request_id}] Async client error: {error_detail}")
                raise ValueError(f"API client error: {error_detail}")
            
            resp.raise_for_status()
            
            # Validate JSON
            try:
                return resp.json()
            except json.JSONDecodeError:
                logger.error(f"[{request_id}] Invalid JSON in async response")
                raise ValueError("API returned invalid JSON")
            
        except httpx.TimeoutException:
            logger.error(f"[{request_id}] Async request timeout")
            raise TimeoutError(f"Request timeout after {self.timeout}s")
            
        except httpx.HTTPStatusError as exc:
            logger.error(f"[{request_id}] Async HTTP error: {exc}")
            raise RuntimeError(f"API error: {exc}")
    
    def refine_query(self, payload: Dict[str, Any]) -> str:
        """
        Refine a claim into an optimized search query.
        Returns the refined query string.
        """
        result = self._post("/evidence/refine-query", payload)
        self._validate_refine_response(result)
        return self._extract_refined_query(result, payload["claim"])
    
    def scan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute evidence scan across configured sources.
        Returns complete scan results with snapshot.
        """
        result = self._post("/evidence/scan", payload)
        self._validate_scan_response(result)
        return result
    
    async def refine_and_scan_parallel(
        self,
        payload: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Execute refine and scan operations in parallel.
        Returns tuple of (refined_query, scan_results).
        """
        refined, scan = await asyncio.gather(
            self._async_post("/evidence/refine-query", payload),
            self._async_post("/evidence/scan", payload),
            return_exceptions=True
        )
        
        if isinstance(refined, Exception):
            raise refined
        if isinstance(scan, Exception):
            raise scan
        
        self._validate_refine_response(refined)
        self._validate_scan_response(scan)
        
        refined_query = self._extract_refined_query(refined, payload["claim"])
        return refined_query, scan
    
    @staticmethod
    def _extract_refined_query(response: Dict[str, Any], fallback: str) -> str:
        """Extract refined query from API response with fallback."""
        return (
            response.get("refined_query") or
            response.get("query_text") or
            fallback
        )
    
    @staticmethod
    def _generate_request_id(payload: Dict[str, Any]) -> str:
        """Generate deterministic request ID for logging and caching."""
        stable_payload = {
            k: v for k, v in sorted(payload.items())
            if k not in ['timestamp', 'request_id']
        }
        canonical = json.dumps(stable_payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]
    
    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        """Extract error message from response."""
        try:
            error_data = response.json()
            return error_data.get('detail') or error_data.get('message') or response.text
        except:
            return response.text[:200]
    
    @staticmethod
    def _extract_error_message_async(response: httpx.Response) -> str:
        """Extract error message from async response."""
        try:
            error_data = response.json()
            return error_data.get('detail') or error_data.get('message') or response.text
        except:
            return response.text[:200]
    
    @staticmethod
    def _validate_refine_response(response: Dict[str, Any]):
        """Validate refine query response structure."""
        if not isinstance(response, dict):
            raise ValueError("Invalid refine response: not a dictionary")
        
        if not any(key in response for key in ['refined_query', 'query_text']):
            raise ValueError("Invalid refine response: missing query field")
    
    @staticmethod
    def _validate_scan_response(response: Dict[str, Any]):
        """Validate scan response structure."""
        if not isinstance(response, dict):
            raise ValueError("Invalid scan response: not a dictionary")
        
        if 'snapshot' not in response:
            raise ValueError("Invalid scan response: missing snapshot")
        
        snapshot = response['snapshot']
        required_fields = ['support_level', 'combined_count']
        
        for field in required_fields:
            if field not in snapshot:
                raise ValueError(f"Invalid scan response: missing {field} in snapshot")

# Initialize API client
api = EcoSentiaAPI()

# ============================================================================
# CACHING UTILITIES
# ============================================================================

def generate_cache_key(payload: Dict[str, Any]) -> str:
    """Generate deterministic cache key from payload."""
    stable_payload = {
        k: v for k, v in sorted(payload.items())
        if k not in ['timestamp', 'request_id']
    }
    canonical = json.dumps(stable_payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

@st.cache_data(ttl=settings.cache_ttl, show_spinner=False)
def cached_scan(cache_key: str, payload_json: str) -> Dict[str, Any]:
    """
    Cache scan results to avoid redundant API calls.
    TTL set to 1 hour by default.
    
    Args:
        cache_key: Deterministic cache key
        payload_json: JSON string of payload
    """
    payload = json.loads(payload_json)
    return api.scan(payload)

# ============================================================================
# SESSION STATE MANAGEMENT
# ============================================================================

def initialize_session_state():
    """Initialize all required session state variables."""
    defaults = {
        "domain_mode": "Fog",
        "lens_ui": "Mechanism",
        "source": "Both",
        "max_results": 5,
        "panels": {},
        "history": [],
        "panel_counter": 0,
        "panel_claims": {},
        "initialized": True
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def get_panel_state(panel_id: str) -> PanelState:
    """Get or create panel state for given panel ID."""
    if panel_id not in st.session_state.panels:
        st.session_state.panels[panel_id] = PanelState()
    return st.session_state.panels[panel_id]

def save_to_history(
    state: PanelState,
    claim: str,
    preset: str,
    lens: str
):
    """Save completed evaluation to session history."""
    if state.scan and "snapshot" in state.scan:
        entry = EvaluationHistory(
            timestamp=datetime.now(),
            claim=claim,
            preset=preset,
            lens=lens,
            support_level=state.scan["snapshot"].get("support_level", "none"),
            snapshot=state.scan["snapshot"]
        )
        st.session_state.history.append(entry)
        
        # Keep only last N entries to prevent memory issues
        if len(st.session_state.history) > settings.max_history_entries:
            st.session_state.history = st.session_state.history[-settings.max_history_entries:]
        
        logger.info(f"Saved evaluation to history: {claim[:50]}...")

def export_history_json() -> str:
    """Export history as JSON string."""
    history_data = [entry.to_dict() for entry in st.session_state.history]
    return json.dumps(history_data, indent=2, ensure_ascii=False)

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_sidebar():
    """Render sidebar with global controls and history."""
    with st.sidebar:
        st.title("EcoSentia Evaluation")
        
        # Global settings
        st.session_state.domain_mode = st.selectbox(
            "Domain Preset",
            ["Fog", "EV", "Custom"],
            index=["Fog", "EV", "Custom"].index(st.session_state.domain_mode),
            help="Select the domain-specific evaluation preset"
        )
        
        st.session_state.lens_ui = st.selectbox(
            "Evaluation Lens",
            ["Mechanism", "Context", "Scale", "Manufacturability", "Safety"],
            index=["Mechanism", "Context", "Scale", "Manufacturability", "Safety"].index(
                st.session_state.lens_ui
            ),
            help="Choose the analytical perspective for evaluation"
        )
        
        st.session_state.source = st.selectbox(
            "Evidence Source",
            ["Both", "PubMed", "OpenAlex"],
            index=["Both", "PubMed", "OpenAlex"].index(st.session_state.source),
            help="Select which databases to search"
        )
        
        st.session_state.max_results = st.slider(
            "Max Results",
            min_value=1,
            max_value=10,
            value=st.session_state.max_results,
            help="Maximum number of evidence records to retrieve"
        )
        
        st.divider()
        
        # History section
        if st.session_state.history:
            st.subheader(f"History ({len(st.session_state.history)})")
            
            # Export button
            if st.button("Export History", use_container_width=True):
                history_json = export_history_json()
                st.download_button(
                    label="Download JSON",
                    data=history_json,
                    file_name=f"ecosentia_history_{datetime.now():%Y%m%d_%H%M%S}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            # Clear history button
            if st.button("Clear History", use_container_width=True):
                st.session_state.history = []
                st.rerun()
            
            st.divider()
            
            # Show recent entries
            with st.expander("Recent Evaluations", expanded=False):
                for i, entry in enumerate(reversed(st.session_state.history[-10:])):
                    st.caption(
                        f"**{entry.timestamp:%Y-%m-%d %H:%M}**"
                    )
                    st.caption(
                        f"{entry.preset} | {entry.lens} | "
                        f"Support: {entry.support_level.upper()}"
                    )
                    st.caption(f"_{entry.claim[:60]}..._")
                    
                    if i < len(st.session_state.history) - 1:
                        st.divider()

def render_panel(panel_id: str, claim_text: str):
    """
    Render a single evaluation panel with all controls and results.
    
    Args:
        panel_id: Unique identifier for this panel
        claim_text: The claim text to evaluate
    """
    state = get_panel_state(panel_id)
    
    # Error boundary wrapper
    try:
        _render_panel_content(panel_id, claim_text, state)
    except Exception as exc:
        logger.error(f"Panel {panel_id} render error: {exc}", exc_info=True)
        st.error(f"Panel error: {exc}")
        
        if st.button("Reset Panel", key=f"reset_error_{panel_id}"):
            state.reset()
            st.rerun()

def _render_panel_content(panel_id: str, claim_text: str, state: PanelState):
    """Internal panel rendering logic."""
    
    st.markdown(
        f'<div role="region" aria-label="Evaluation Panel {panel_id}">',
        unsafe_allow_html=True
    )
    
    # Panel header with close button
    col_header, col_close = st.columns([5, 1])
    
    with col_header:
        st.subheader(f"Panel {panel_id.split('_')[1]}")
    
    with col_close:
        if st.button("✕", key=f"close_{panel_id}", help="Close this panel"):
            del st.session_state.panels[panel_id]
            del st.session_state.panel_claims[panel_id]
            st.rerun()
    
    # Display claim
    st.text_area(
        "Claim",
        value=claim_text,
        height=100,
        key=f"claim_display_{panel_id}",
        disabled=True
    )
    
    # Validate and prepare payload
    try:
        request = EvaluationRequest(
            claim=claim_text,
            preset=st.session_state.domain_mode,
            lens=st.session_state.lens_ui.lower(),
            source=st.session_state.source,
            max_results=st.session_state.max_results
        )
        payload = request.dict()
    except ValidationError as exc:
        st.error(f"Invalid input: {exc}")
        return
    
    # Disable buttons during processing
    is_disabled = state.is_processing
    
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button(
            "Refine Query",
            key=f"refine_{panel_id}",
            disabled=is_disabled,
            use_container_width=True
        ):
            state.is_processing = True
            state.error = None
            
            with st.spinner("Refining query..."):
                try:
                    state.refined_query = api.refine_query(payload)
                    state.last_updated = datetime.now()
                    logger.info(f"Panel {panel_id}: Query refined successfully")
                    st.success("Query refined successfully")
                    
                except Exception as exc:
                    state.error = f"Refine failed: {str(exc)}"
                    logger.error(f"Panel {panel_id}: Refine failed - {exc}")
                    st.error(f"Refine failed: {exc}")
                    
                finally:
                    state.is_processing = False
                    st.rerun()
    
    with col2:
        if st.button(
            "Execute Scan",
            key=f"scan_{panel_id}",
            disabled=is_disabled,
            use_container_width=True,
            type="primary"
        ):
            state.is_processing = True
            state.error = None
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Step 1: Refine query if not already done
                if not state.refined_query:
                    status_text.text("Refining query...")
                    progress_bar.progress(0.3)
                    state.refined_query = api.refine_query(payload)
                else:
                    progress_bar.progress(0.3)
                
                # Step 2: Execute scan
                status_text.text("Scanning evidence sources...")
                progress_bar.progress(0.6)
                
                scan_payload = {**payload, "query_text": state.refined_query}
                cache_key = generate_cache_key(scan_payload)
                payload_json = json.dumps(scan_payload, sort_keys=True)
                
                state.scan = cached_scan(cache_key, payload_json)
                
                # Step 3: Complete
                status_text.text("Processing results...")
                progress_bar.progress(1.0)
                
                state.last_updated = datetime.now()
                save_to_history(state, claim_text, payload["preset"], payload["lens"])
                
                logger.info(f"Panel {panel_id}: Scan completed successfully")
                st.success("Scan completed successfully")
                
            except Exception as exc:
                state.error = f"Scan failed: {str(exc)}"
                logger.error(f"Panel {panel_id}: Scan failed - {exc}")
                st.error(f"Scan failed: {exc}")
                
            finally:
                state.is_processing = False
                progress_bar.empty()
                status_text.empty()
                st.rerun()
    
    with col3:
        if st.button(
            "Reset",
            key=f"reset_{panel_id}",
            disabled=is_disabled,
            use_container_width=True
        ):
            state.reset()
            logger.info(f"Panel {panel_id}: State reset")
            st.rerun()
    
    # Display error if present
    if state.error:
```python
    if state.error:
        st.error(state.error)

    # Display refined query
    if state.refined_query:
        with st.expander("Refined Query", expanded=False):
            st.code(state.refined_query, language="text")

    # Display scan results
    if state.scan and "snapshot" in state.scan:
        snapshot = state.scan["snapshot"]

        st.markdown("### Evidence Summary")

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Support Level", snapshot.get("support_level", "N/A").upper())
        col_b.metric("Total Evidence", snapshot.get("combined_count", 0))
        col_c.metric("Sources Queried", snapshot.get("sources_queried", "N/A"))

        # Optional detailed breakdown
        with st.expander("Detailed Snapshot", expanded=False):
            st.json(snapshot)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def render_main_content():
    """Render main application interface."""
    initialize_session_state()

    st.title("EcoSentia Evaluation Platform")
    st.caption("Scientific Claim Evaluation with Multi-Source Evidence Scanning")

    st.divider()

    # Add new panel section
    st.subheader("Add New Evaluation")

    new_claim = st.text_area(
        "Enter scientific claim",
        height=100,
        key="new_claim_input",
        placeholder="Enter a detailed scientific or technical claim..."
    )

    if st.button("Add Panel", type="primary", use_container_width=True):
        if not new_claim.strip():
            st.warning("Please enter a valid claim.")
        else:
            panel_id = f"panel_{st.session_state.panel_counter}"
            st.session_state.panel_claims[panel_id] = new_claim.strip()
            st.session_state.panel_counter += 1
            st.session_state.new_claim_input = ""
            logger.info(f"New panel created: {panel_id}")
            st.rerun()

    st.divider()

    # Render active panels
    if not st.session_state.panel_claims:
        st.info("No active evaluation panels. Add a claim to begin.")
    else:
        for panel_id, claim_text in list(st.session_state.panel_claims.items()):
            with st.container():
                render_panel(panel_id, claim_text)
                st.divider()

    # Footer
    st.markdown("---")
    st.caption(
        f"EcoSentia Platform | Session Evaluations: {len(st.session_state.history)}"
    )


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

def main():
    """Application entry point."""
    try:
        render_sidebar()
        render_main_content()
    except Exception as exc:
        logger.critical(f"Critical application error: {exc}", exc_info=True)
        st.error("A critical application error occurred. Please refresh the page.")


if __name__ == "__main__":
    main()
```