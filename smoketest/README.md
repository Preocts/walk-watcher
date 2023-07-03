# Smoketest

This smoketest simulates three directory queues with a total of 12 directories
to watch. Documents are generated and enter the queue with a timestamp for their
processing time. As the timestamp expires the document is moved to the next
stage of the queue. At the end of the queue the doucment is removed (deleted).
Each document has a 10% chance of failure *each time it moves between queues*
with a total of three retry attempts prior to hitting the dead-letter queue. No
reprocessing occures once in dead-letter. All files and directories in regards
to the mock queue are removed upon exit of the smoketest.

Example view of a smoketest queue state:

```console
Directory: initial_documents
        initial_documents_stage1: 72
        initial_documents_stage2: 85
        initial_documents_stage3: 93
        retry: 42
        dead_letter: 6
        total processed: 511
Directory: final_documents
        final_documents: 82
        final_documents_stage2: 56
        retry: 26
        dead_letter: 2
        total processed: 547
Directory: additional_documents
        additional_documents: 43
        retry: 4
        dead_letter: 1
        total processed: 706
```

---

## Running the smoketest

1. Ensure the root package has been installed with `make install-dev`
2. Configure the `smoketest.ini` to the desired outcome
3. Run `python smoketest_watcher.py` from within the `./smoketest` directory
4. Use `CTRL - C` to exit the smoketest


Example console output:

- Metrics are gathered every five (5) seconds
- Metrics are emitted every sixty (60) seconds

```console
Running smoketest watcher
2023-07-02 16:33:20,704 Running watcher...
2023-07-02 16:33:20,795 Watcher finished in 0.09011784399626777 seconds
2023-07-02 16:33:20,795 Detected 12 directories
2023-07-02 16:33:20,795 Detected 580 files
Running smoketest watcher
2023-07-02 16:33:25,806 Running watcher...
2023-07-02 16:33:25,893 Watcher finished in 0.0865441720088711 seconds
2023-07-02 16:33:25,893 Detected 12 directories
2023-07-02 16:33:25,893 Detected 517 files
Emitting smoketest watcher metrics
2023-07-02 16:33:28,900 Emitting metrics...
2023-07-02 16:33:28,900 Emitted 274 metric lines.
2023-07-02 16:33:28,900 Emitting finished in 0.0008130589994834736 seconds
```
