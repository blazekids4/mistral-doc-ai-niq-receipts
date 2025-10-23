import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import AzureOpenAI

from storage_utils import get_blob_base64, get_container_blobs

load_dotenv()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _sanitize_for_filename(value: str) -> str:
    """Convert blob identifiers into filesystem-safe names."""
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return sanitized.strip("_") or "blob"


def _save_response_files(
    blob_name: str,
    content_type: str,
    deployment: str,
    response,
    result_text: str,
) -> None:
    """Persist raw JSON and markdown outputs for later analysis."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"Failed to create data directory '{DATA_DIR}': {exc}")
        return

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    flattened_name = blob_name.replace("\\", "/")
    safe_blob_name = _sanitize_for_filename(flattened_name)
    filename_root = f"{timestamp}_{safe_blob_name}"

    json_path = DATA_DIR / f"{filename_root}.json"
    markdown_path = DATA_DIR / f"{filename_root}.md"

    try:
        raw_response = response.model_dump()  # type: ignore[attr-defined]
    except AttributeError:
        try:
            raw_response = response.to_dict()  # type: ignore[attr-defined]
        except AttributeError:
            try:
                raw_response = json.loads(response.model_dump_json())  # type: ignore[attr-defined]
            except Exception:
                raw_response = str(response)

    payload = {
        "blob_name": blob_name,
        "content_type": content_type,
        "deployment": deployment,
        "timestamp_utc": timestamp,
        "response": raw_response,
        "text": result_text,
    }

    json_written = False
    markdown_written = False

    try:
        with json_path.open("w", encoding="utf-8") as file_handle:
            json.dump(payload, file_handle, indent=2)
        json_written = True
    except Exception as exc:
        print(f"Failed to write JSON output for {blob_name}: {exc}")

    try:
        with markdown_path.open("w", encoding="utf-8") as file_handle:
            file_handle.write(result_text or "")
        markdown_written = True
    except Exception as exc:
        print(f"Failed to write markdown output for {blob_name}: {exc}")

    if json_written and markdown_written:
        try:
            json_rel = json_path.relative_to(DATA_DIR.parent)
            md_rel = markdown_path.relative_to(DATA_DIR.parent)
            print(f"Saved outputs to {json_rel} and {md_rel}")
        except ValueError:
            print(f"Saved outputs to {json_path} and {markdown_path}")


def _resolve_content_type(blob_name: str) -> str:
    """Choose a sensible content type based on file extension."""
    extension = os.path.splitext(blob_name.lower())[1]
    if extension == ".png":
        return "image/png"
    if extension == ".pdf":
        return "application/pdf"
    return "image/jpeg"


def _create_client(endpoint: str, api_key: str, api_version: str) -> Optional[AzureOpenAI]:
    """Build an Azure OpenAI client when configuration is present."""
    if not endpoint or not api_key:
        print("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in your environment")
        return None

    try:
        return AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
        )
    except Exception as exc:
        print(f"Failed to create Azure OpenAI client: {exc}")
        return None


def analyze_blob(blob_name: str, client: AzureOpenAI, deployment: str) -> None:
    """Send a single blob through the Azure OpenAI vision model."""
    base64_image = get_blob_base64(blob_name)
    if not base64_image:
        print(f"Skipping {blob_name} - blob appears empty")
        return

    content_type = _resolve_content_type(blob_name)

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "carefully analyze the image of a receipt and extract the exact content.  if parts of the receipt are blurred or unclear, do spend more time on those areas and try to resolve the lack of clarity by both zooming in and enhancing the image, as well as referencing the overall context.  do not make up any content that is not clearly present on the receipt.  return the full text of the receipt in markdown format. if you are unable to confidently decifer any part of the receipt, return '[unreadable]' in place of that content."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{base64_image}",
                                "detail": "high"
                            },
                        },
                    ],
                }
            ],
        )
    except Exception as exc:
        print(f"Azure OpenAI request for {blob_name} failed: {exc}")
        return

    result_text = response.choices[0].message.content if response.choices else "<no content>"
    print("\n========================================")
    print(f"Blob: {blob_name}")
    print(result_text)

    _save_response_files(blob_name, content_type, deployment, response, result_text)


def main() -> None:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = "2024-12-01-preview"

    if not deployment:
        print("AZURE_OPENAI_DEPLOYMENT must be set in your environment")
        return

    client = _create_client(endpoint, subscription_key, api_version)
    if not client:
        return

    blob_names = get_container_blobs()
    if not blob_names:
        print("No blobs found with the configured prefix; update STORAGE_* env vars if needed")
        return

    print(f"Found {len(blob_names)} blobs to analyze\n")
    for blob_name in blob_names:
        analyze_blob(blob_name, client, deployment)


if __name__ == "__main__":
    main()