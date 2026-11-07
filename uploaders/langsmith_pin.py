"""Pin data/golden/v1.jsonl as the LangSmith dataset settlement-grader-golden.

The owner runs this. Nothing in scorer/ or the tests imports it. langsmith is
imported only after v1's bytes match v1.sha256, so a refusal needs no package
(ruling 6). The key is read by the client from the environment and is never
printed.

Calls, from the LangSmith Python SDK:

- Client.create_dataset: https://reference.langchain.com/python/langsmith/client/Client/create_dataset
- Client.create_example (outputs is the documented alias of reference_outputs):
  https://reference.langchain.com/python/langsmith/client/Client/create_example
- Client.list_dataset_versions, each DatasetVersion with its exact as_of:
  https://reference.langchain.com/python/langsmith/client/Client/list_dataset_versions
- Client.update_dataset_tag returns None and needs a version's exact as_of, which
  its documentation says to take from a version lookup, not from the dataset:
  https://reference.langchain.com/python/langsmith/client/Client/update_dataset_tag
- Client.read_dataset_version(dataset_id=..., tag="v1"):
  https://reference.langchain.com/python/langsmith/client/Client/read_dataset_version

DatasetVersion carries tags and as_of. That pair is the version this script prints.
"""
import hashlib
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HASH_LINE = "%s  data/golden/v1.jsonl\n"


def v1_hash_matches(root=None):
    """True only when v1.jsonl's bytes are the digest named in v1.sha256."""
    base = ROOT if root is None else root
    v1_path = os.path.join(base, "data", "golden", "v1.jsonl")
    sha_path = os.path.join(base, "data", "golden", "v1.sha256")
    try:
        with open(v1_path, "rb") as handle:
            data = handle.read()
        with open(sha_path, "r", encoding="utf-8", newline="") as handle:
            line = handle.read()
    except (OSError, UnicodeError):
        return False
    digest = hashlib.sha256(data).hexdigest()
    return line == _HASH_LINE % digest


def _rows(root):
    path = os.path.join(root, "data", "golden", "v1.jsonl")
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip() == "":
                continue
            rows.append(json.loads(line))
    return rows


def main(argv=None):
    root = ROOT
    if not v1_hash_matches(root):
        sys.stderr.write("v1 bytes do not match v1.sha256\n")
        return 2
    import langsmith
    client = langsmith.Client()
    dataset = client.create_dataset("settlement-grader-golden")
    for row in _rows(root):
        client.create_example(
            inputs={"question": row["question"]},
            outputs={
                "ground_truth": row["ground_truth"],
                "expected": row["expected"],
            },
            metadata={
                "case_id": row["case_id"],
                "blend": row["blend"],
                "difficulty": row["difficulty"],
                "intent": row["intent"],
                "segment": row["segment"],
            },
            dataset_id=dataset.id,
        )
    # Each example creates a version. update_dataset_tag needs a version's
    # exact as_of, which only a version lookup carries: the dataset record's
    # own timestamp is not documented as one. This script is not run here.
    versions = list(client.list_dataset_versions(dataset_id=dataset.id))
    if not versions:
        sys.stderr.write("the dataset has no version to tag\n")
        return 2
    latest = max(versions, key=lambda item: item.as_of)
    client.update_dataset_tag(dataset_id=dataset.id, as_of=latest.as_of, tag="v1")
    version = client.read_dataset_version(dataset_id=dataset.id, tag="v1")
    sys.stdout.write("%s\n" % dataset.id)
    sys.stdout.write("%s\n" % version.as_of)
    return 0


if __name__ == "__main__":
    sys.exit(main())
