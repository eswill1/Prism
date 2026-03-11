from dataclasses import dataclass


@dataclass
class PipelineStatus:
    stage: str
    state: str


def main() -> None:
    stages = [
        PipelineStatus("ingestion", "planned"),
        PipelineStatus("story_clustering", "planned"),
        PipelineStatus("perspective_assembly", "planned"),
        PipelineStatus("context_pack_generation", "planned"),
    ]

    print("Prism ML scaffold")
    for stage in stages:
        print(f"- {stage.stage}: {stage.state}")


if __name__ == "__main__":
    main()
