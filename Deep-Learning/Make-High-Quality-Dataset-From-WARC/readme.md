# Make High Quality Dataset from WARC for Pre-training

In the following subsections, we will explain each step involved in generating High Qualit dataset Pre-training


## How to evaluate the quality of training data?

### Using a "clean" corpus and perplexity check
- Method: Train a model using a high-quality corpus (e.g., Wikipedia) and then use this model to check the perplexity of the new dataset.
- Advantages:
Quick: Can quickly assess the quality of the dataset.
Simple: Relatively simple to implement, does not require complex computational resources.
- Disadvantages:
Limitations: Low perplexity does not necessarily mean better performance on specific tasks.
Single Metric: Perplexity is just a single metric and cannot fully reflect the quality of the dataset.

### Training small models and testing on evaluation tasks
- Method: Extract a portion of data from the dataset, train a small model, and test the model's performance on a set of specific evaluation tasks (e.g., SQuAD, GLUE, etc.).
- Advantages:
Specific: Provides specific performance feedback by testing the model on actual tasks.
Diversity: Allows for the selection of various evaluation tasks to comprehensively assess the dataset quality.
- Disadvantages:
Resource Demand: Requires a certain amount of computational resources and time.
Task Selection: Needs to select diverse and representative evaluation tasks, which may increase complexity.

### Early signal method
- Method: Train a small model and conduct preliminary evaluations on some simple and quick benchmark tasks (e.g., text classification, sentiment analysis, etc.).
- Advantages:
Rapid Iteration: Quickly obtain initial feedback, facilitating rapid iteration and optimization.
Suitable for Early Stages: Helps quickly screen datasets in the early stages of development.
- Disadvantages:
Simple Tasks: These tasks may be relatively simple and may not fully represent the model's performance on complex tasks.
Preliminary Evaluation: Only provides initial performance feedback, which may require further detailed evaluation.

### Using GPT-4 for evaluation
- Method: Use the GPT-4 model to evaluate the new dataset, potentially including various tasks (e.g., text generation, question answering, sentiment analysis, etc.).
Advantages:
High-Quality Evaluation: As a powerful language model, GPT-4 can provide high-quality evaluation results, especially on complex tasks.
Multi-Task Capability: Can evaluate on various tasks, providing comprehensive performance feedback.
Real-World Usage: Evaluation results are closer to actual usage, especially if your final application is also based on similar advanced models.
- Disadvantages:
Computational Resources: Training and evaluating GPT-4 requires a large amount of computational resources and time, which may increase costs.
Complexity: The complexity of GPT-4 means more potential issues during debugging and optimization.
Overfitting Risk: If not careful, there is a risk of over-optimizing specific tasks, leading to poorer performance on other tasks.

### Summary
- Using a "clean" corpus and perplexity check: Suitable for quick, preliminary quality assessment but limited to a single metric.
- Training small models and testing on evaluation tasks: Suitable for scenarios requiring specific task performance feedback but requires more resources and task selection.
- Early signal method: Suitable for the early stages of development to quickly screen datasets but involves simpler tasks.
- Using GPT-4 for evaluation: Suitable for scenarios requiring high-quality and comprehensive evaluation, providing feedback closest to actual usage but with high resource demands.


## Prepare environment
In the following content, I will show how to create High Quality Dataset from WARC.

### Create conda env
```
#conda create --name=dataclean python=3.10  
#conda activate dataclean  
(dataclean) root@david1a100:~# cd dataclean/

(dataclean) root@david1a100:~/dataclean# hostname
david1a100.australiaeast.cloudapp.azure.com

#pip install datatrove xxhash faust-cchardet python-magic warcio fasteners tldextract trafilatura fasttext-wheel nltk awscli fasttext numpy==1.21.0  
#pip install datatrove[all]  
#pip install datatrove trafilatura awscli 
#aws configure  

```
### Download WARC
Access the following link to check WARC file address:
https://data.commoncrawl.org/crawl-data/CC-MAIN-2023-23/index.html

Download this file named warc.paths.gz :

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Make-High-Quality-Dataset-From-WARC/images/1.png)


Check file path just as follwing in warc.paths.gz. There are so many warc.gz files, I only take CC-MAIN-20230527223515-20230528013515-00000.warc.gz as an example. 
```
crawl-data/CC-MAIN-2023-23/segments/1685224643388.45/warc/CC-MAIN-20230527223515-20230528013515-00000.warc.gz
```
Download files as follwing script:
```
(dataclean) root@david1a100:~/dataclean# cat download_warc_file.py
import os
import subprocess

def download_warc_file(url, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Downloading {url}...")
    command = f"wget -P {output_dir} {url}"
    subprocess.run(command, shell=True, check=True)

if __name__ == '__main__':
    # URL of the WARC file
    warc_url = "https://data.commoncrawl.org/crawl-data/CC-MAIN-2023-23/segments/1685224643388.45/warc/CC-MAIN-20230527223515-20230528013515-00000.warc.gz"

    # output directory
    output_dir = "/root/dataclean/data/CC-MAIN-2023-23/segments"

    download_warc_file(warc_url, output_dir)
```
## Basic data processing
After download 00000.warc.gz， I uses the local executor LocalPipelineExecutor to execute the data processing pipeline, which includes the following steps: 
- reading WARC files
- filtering URLs
- extracting content using Trafilatura
- filtering non-English content
- filtering duplicate content
- filtering low-quality content
- writing the processed data to JSONL files.

```
(dataclean) root@david1a100:~/dataclean# cat process_common_crawl_dump.py
```
```
import nltk
import sys
import os
from datatrove.executor.local import LocalPipelineExecutor  
from datatrove.pipeline.extractors import Trafilatura
from datatrove.pipeline.filters import (
    GopherQualityFilter,
    GopherRepetitionFilter,
    LanguageFilter,
    URLFilter,
)
from datatrove.pipeline.readers import WarcReader
from datatrove.pipeline.writers.jsonl import JsonlWriter

def download_punkt():
    nltk.download('punkt')
    nltk.download('punkt_tab')

def set_nltk_data_path():
    nltk.data.path.append('/root/nltk_data')

set_nltk_data_path()
download_punkt()

def main():
    # DUMP should be given as an argument. Example: CC-MAIN-2023-23
    if len(sys.argv) != 2:
        print("Argument required: dump name")
        sys.exit(-1)

    DUMP = sys.argv[1]
    MAIN_OUTPUT_PATH = "./output"  # Local Output Path
    DATA_PATH = f"./data/{DUMP}/segments/"

    print(f"Checking files in {DATA_PATH}")
    for root, dirs, files in os.walk(DATA_PATH):
        print(f"Found directory: {root}")
        for file in files:
            print(f"Found file: {file}")

    if not any(os.scandir(DATA_PATH)):
        print(f"No files found in {DATA_PATH}")
        sys.exit(-1)
        
    def initializer():
        set_nltk_data_path()
        download_punkt()

    from multiprocessing import Pool

    with Pool(processes=8, initializer=initializer) as pool:
        executor = LocalPipelineExecutor(  
            pipeline=[
                WarcReader(
                    DATA_PATH,  
                    glob_pattern="*.warc.gz", 
                    default_metadata={"dump": DUMP},
                ),
                URLFilter(exclusion_writer=JsonlWriter(f"{MAIN_OUTPUT_PATH}/removed/url/{DUMP}")),
                Trafilatura(favour_precision=True),
                LanguageFilter(
                    exclusion_writer=JsonlWriter(
                        f"{MAIN_OUTPUT_PATH}/non_english/",
                        output_filename="${language}/" + DUMP + "/${rank}.jsonl.gz",  # 文件夹结构：language/dump/file
                    )
                ),
                GopherRepetitionFilter(exclusion_writer=JsonlWriter(f"{MAIN_OUTPUT_PATH}/removed/repetitive/{DUMP}")),
                GopherQualityFilter(exclusion_writer=JsonlWriter(f"{MAIN_OUTPUT_PATH}/removed/quality/{DUMP}")),
                JsonlWriter(f"{MAIN_OUTPUT_PATH}/output/{DUMP}"),
            ],
            tasks=8,  # Number of local tasks, adjusted to your VM configuration
            logging_dir=f"{MAIN_OUTPUT_PATH}/logs/base_processing/{DUMP}",
        )

        executor.run()

if __name__ == '__main__':
    main()
```
Run script as following:
```
#python3 process_common_crawl_dump.py CC-MAIN-2023-23
```
Script will run for 26 minutes, final output is as follwing:
```
2024-08-14 05:11:53.451 | INFO     | datatrove.utils.logging:add_task_logger:47 - Launching pipeline for rank=0
2024-08-14 05:11:53.452 | INFO     | datatrove.utils.logging:log_pipeline:76 -
--- 🛠️ PIPELINE 🛠
📖 - READER: 🕷 Warc
🔻 - FILTER: 😈 Url-filter
🛢 - EXTRAC: ⛏ Trafilatura
🔻 - FILTER: 🌍 Language ID
🔻 - FILTER: 👯 Gopher Repetition
🔻 - FILTER: 🥇 Gopher Quality
💽 - WRITER: 🐿 Jsonl
2024-08-14 05:11:53.452 | INFO     | datatrove.pipeline.readers.base:read_files_shard:193 - Reading input file CC-MAIN-20230527223515-20230528013515-00000.warc.gz
[nltk_data]   Package punkt is already up-to-date!
[nltk_data] Downloading package punkt_tab to /root/nltk_data...
[nltk_data]   Package punkt_tab is already up-to-date!
2024-08-14 05:11:55.704 | WARNING  | datatrove.pipeline.extractors.base:run:60 - ❌ Error "" while cleaning record text. Skipping record.
...
2024-08-14 05:38:47.661 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 8/8 tasks completed.
2024-08-14 05:38:47.686 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 8 tasks 📉📉📉

Total Runtime: 26 minutes and 36 seconds

📖 - READER: 🕷 Warc
    Runtime: (2.11%) 33 seconds [0.29 milliseconds±3.12 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 4795961005 [min=1, max=1048576, 140974.75±182620/doc], documents: 34019 [34019.00/input_file]}
🔻 - FILTER: 😈 Url-filter
    Runtime: (0.35%) 5 seconds [0.16 milliseconds±11.08 milliseconds/doc]
    Stats: {total: 34020, forwarded: 33834, doc_len: 4776069530 [min=1, max=1048576, 141161.84±182866/doc], dropped: 186, dropped_domain: 90, dropped_hard_blacklisted: 67, dropped_blacklisted_subword: 21, dropped_soft_blacklisted: 6, dropped_subdomain: 2}
🛢 - EXTRAC: ⛏ Trafilatura
    Runtime: (75.94%) 20 minutes and 12 seconds [35.84 milliseconds±29.25 milliseconds/doc]
    Stats: {total: 33834, forwarded: 27384, doc_len: 57232496 [min=1, max=551300, 2090.00±6280/doc], dropped: 4168}
🔻 - FILTER: 🌍 Language ID
    Runtime: (0.91%) 14 seconds [0.53 milliseconds±2.54 milliseconds/doc]
    Stats: {total: 27384, dropped: 16500, forwarded: 10884, doc_len: 24989254 [min=2, max=73080, 2295.96±4166/doc]}
🔻 - FILTER: 👯 Gopher Repetition
    Runtime: (13.00%) 3 minutes and 27 seconds [19.07 milliseconds±33.46 milliseconds/doc]
    Stats: {total: 10884, forwarded: 8161, doc_len: 21401662 [min=5, max=73080, 2622.43±4274/doc], dropped: 2723, dropped_top_4_gram: 345, dropped_dup_line_frac: 633, dropped_top_2_gram: 796, dropped_duplicated_5_n_grams: 281, dropped_top_3_gram: 399, dropped_duplicated_6_n_grams: 25, dropped_dup_line_char_frac: 173, dropped_duplicated_8_n_grams: 13, dropped_duplicated_10_n_grams: 16, dropped_duplicated_9_n_grams: 23, dropped_duplicated_7_n_grams: 19}
🔻 - FILTER: 🥇 Gopher Quality
    Runtime: (7.55%) 2 minutes [14.76 milliseconds±8.44 milliseconds/doc]
    Stats: {total: 8161, dropped: 2433, dropped_gopher_too_many_end_ellipsis: 232, dropped_gopher_below_alpha_threshold: 1201, forwarded: 5728, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc], dropped_gopher_short_doc: 941, dropped_gopher_too_many_bullets: 49, dropped_gopher_enough_stop_words: 6, dropped_gopher_below_avg_threshold: 1, dropped_gopher_too_many_ellipsis: 1, dropped_gopher_too_many_hashes: 2}
💽 - WRITER: 🐿 Jsonl
    Runtime: (0.14%) 2 seconds [0.40 milliseconds±0.60 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 5728, total: 5728, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc]}
```
### Check data processing results

```
root@david1a100:~/dataclean/output/output/CC-MAIN-2023-23# zcat ./00000.jsonl.gz | head -n 2 | jq .
```
Output:
```
{
  "text": "Buy Ambien Online Legally (Zolpidem) belongs to the imidazopyridines class of opioids. Ambien complements the exceptional of sleep via way of means of decreasing the time it takes to fall asleep, decreasing the frequency of nocturnal awakenings, and growing the general period of sleep. Lengthens the second one degree of sleep and the deep sleep degree (III and IV). It does now no longer make you sleepy throughout the day. If you’re seeking to Buy Ambien Online at an inexpensive cost, come to our on line pharmacy.",
  "id": "<urn:uuid:dd20979b-ada8-4c5b-b53e-4ade7274bc1b>",
  "metadata": {
    "dump": "CC-MAIN-2023-23",
    "url": "http://42627.dynamicboard.de/u101117_ambienusa.html",
    "date": "2023-05-27T23:12:51Z",
    "file_path": "/root/dataclean/data/CC-MAIN-2023-23/segments/CC-MAIN-20230527223515-20230528013515-00000.warc.gz",
    "language": "en",
    "language_score": 0.8990675806999207
  }
}
{
  "text": "My little guy turned two over the summer and we celebrated with an oh-so-cute Golf Birthday Party. He is all boy and loves anything that includes a stick and ball, which made choosing the golf theme fairly easy. We had fun golfing games, snacks & treats and each little caddie even received there very own golf bag. The post was getting fairly large I decided to split it in two parts. Part one covers the favor and dessert table and part two will focus on the food and games. Enjoy!\nGolf Pro Shop for the favor table\nEach “Golf Pro” received his/her own set of golf clubs (thank you Target dollar section for saving the day!), a blue or green visor I purchased at Joann’s, practice golf balls and a water bottle to stay hydrated on the course.\nI created the backdrop for the dessert table with a tan table cloth I had and pinned it to the window frame with thumb tacks (my husband wasn’t too happy about that one…opps!) I used 12” white tissue paper balls that I purchased from Devra Party and hung them by grosgrain ribbon.\nI wanted to use items on the dessert table that went along with the theme so I racked my brain for some golf terms. The sign over the table was “Caddie’s Sweet Spot” (sweet spot refers to the center point of the face of the club).\nThere was a “water hazard” ~ blue jell-o jigglers, “wormburners” (which is the term for a ball that skims the grass) ~ chocolate pudding pack topped with crumbled Oreos and gummy worms plus a sand trap of “doughnut hole in one” ~ made with powder sugar doughnuts and crumbled graham crackers for the sand.\nI also made cake pops that resembled golf balls ~ some like a lollipop and others with a golf flag and the number two for the birthday boy. The kids had a few candy choices and a small bag to fill so they could bring treats home.\n“Wormburners” – Chocolate pudding cups topped with crushed oreos and gummy worms\nGreen Grass Cupcakes, with white gumball and printable golf flags.\nThank you so much to everyone who helped make this party amazing, I couldn’t have done it without you.\nVendor List:\nPhotography: Andary Studio\nParty Printables: Printable Studio by 505 Design, Inc\nGolf Club Sets: Target Dollar Section\nFoam Visors: Joann’s\nGreen & White Tissue Balls: Devra Party\nGreen Polka Dot Balloons: Paws Attraction Boutique\nCupcakes – My super talented sister\nInterested in hosting your own Golf Themed Party – Check out the Golf Pro Printable set now available in the shop.\nMore details coming soon….\nThanks for stopping by! Cathy C.",
  "id": "<urn:uuid:9ad54ec1-b946-4293-8099-abc434ef154c>",
  "metadata": {
    "dump": "CC-MAIN-2023-23",
    "url": "http://505-design.com/tag/boys-party/",
    "date": "2023-05-27T23:24:49Z",
    "file_path": "/root/dataclean/data/CC-MAIN-2023-23/segments/CC-MAIN-20230527223515-20230528013515-00000.warc.gz",
    "language": "en",
    "language_score": 0.9405166506767273
  }
}
```

## Minhash deduplication

I use the local executor `LocalPipelineExecutor` to execute the data deduplication pipeline, which includes the following steps:

- **Configuring Minhash**: Setting up Minhash with 64-bit hashes for better precision and fewer false positives (collisions).

- **Reading Input Data**: Using `JsonlReader` to read input data from a specified directory.

- Stage 1: Calculating Minhash Signatures:

  - **Pipeline**: Reads input data and calculates Minhash signatures.
  - **Output**: Stores signatures in a specified folder.
  - **Tasks**: Configured to run with a specified number of tasks based on the local environment.

- Stage 2: Finding Matches Between Signatures in Each Bucket :

  - **Pipeline**: Processes the signatures to find matches within each bucket.
  - **Output**: Stores bucketed signatures in a specified folder.
  - **Tasks**: Runs with a number of tasks equal to the number of buckets.
  - **Dependency**: Depends on the completion of Stage 1.

- Stage 3: Creating Clusters of Duplicates:

  - **Pipeline**: Uses the results from all buckets to create clusters of duplicate items.
  - **Output**: Stores IDs of items to be removed in a specified folder.
  - **Tasks**: Runs as a single task.
  - **Dependency**: Depends on the completion of Stage 2.

- Stage 4: Filtering Out Duplicates:

  - **Pipeline**: Reads the original input data, counts tokens, filters out duplicates (keeping only one sample per cluster), and writes the deduplicated data to JSONL files.
  - **Output**: Stores deduplicated output and removed items in specified folders.
  - **Tasks**: Configured to run with a specified number of tasks.
  - **Dependency**: Depends on the completion of Stage 3.


```
root@david1a100:~/dataclean# cat minhash_deduplication.py
```
```
from datatrove.executor.local import LocalPipelineExecutor
from datatrove.pipeline.dedup import MinhashDedupSignature
from datatrove.pipeline.dedup.minhash import (
    MinhashConfig,
    MinhashDedupBuckets,
    MinhashDedupCluster,
    MinhashDedupFilter,
)
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.tokens import TokensCounter
from datatrove.pipeline.writers.jsonl import JsonlWriter

def main():
    minhash_config = MinhashConfig(use_64bit_hashes=True)  

    LOCAL_MINHASH_BASE_PATH = "./minhash"
    LOCAL_LOGS_FOLDER = "./logs"
    TOTAL_TASKS = 8  

    # Input data path
    INPUT_READER = JsonlReader("./output/output/CC-MAIN-2023-23/")

    # Stage 1: Calculate the Minhash signature for each task
    stage1 = LocalPipelineExecutor(
        pipeline=[
            INPUT_READER,
            MinhashDedupSignature(output_folder=f"{LOCAL_MINHASH_BASE_PATH}/signatures", config=minhash_config),
        ],
        tasks=TOTAL_TASKS,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/signatures",
    )

    # Stage 2: Finding matches between signatures in each bucket
    stage2 = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupBuckets(
                input_folder=f"{LOCAL_MINHASH_BASE_PATH}/signatures",
                output_folder=f"{LOCAL_MINHASH_BASE_PATH}/buckets",
                config=minhash_config,
            ),
        ],
        tasks=minhash_config.num_buckets,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/buckets",
        depends=stage1,
    )

    # Stage 3: Create clusters of duplicate items using the results of all buckets
    stage3 = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupCluster(
                input_folder=f"{LOCAL_MINHASH_BASE_PATH}/buckets",
                output_folder=f"{LOCAL_MINHASH_BASE_PATH}/remove_ids",
                config=minhash_config,
            ),
        ],
        tasks=1,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/clusters",
        depends=stage2,
    )

    # Stage 4: Read raw input data and remove all samples from each duplicate cluster (keep only one)
    stage4 = LocalPipelineExecutor(
        pipeline=[
            INPUT_READER,
            TokensCounter(),  # View the number of tokens before and after de-duplication
            MinhashDedupFilter(
                input_folder=f"{LOCAL_MINHASH_BASE_PATH}/remove_ids",
                exclusion_writer=JsonlWriter(f"{LOCAL_MINHASH_BASE_PATH}/removed"),
            ),
            JsonlWriter(output_folder=f"{LOCAL_MINHASH_BASE_PATH}/deduplicated_output"),
        ],
        tasks=TOTAL_TASKS,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/filter",
        depends=stage3,
    )

    stage4.run()

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
```
Run code:
```
(dataclean) root@david1a100:~/dataclean# python minhash_deduplication.py
```
Results are as following:
```
--- 🛠️ PIPELINE 🛠
📖 - READER: 🐿 Jsonl
🔢 - TOKENIZER: 📊 Counter
🫂 - DEDUP: 🎯 MinHash stage 4
💽 - WRITER: 🐿 Jsonl
2024-08-14 07:20:58.795 | INFO     | datatrove.pipeline.readers.base:read_files_shard:193 - Reading input file 00000.jsonl.gz
2024-08-14 07:20:58.802 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 1/8 tasks completed.
2024-08-14 07:20:58.804 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 2/8 tasks completed.
2024-08-14 07:20:58.805 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 3/8 tasks completed.
2024-08-14 07:20:58.807 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 4/8 tasks completed.
2024-08-14 07:20:58.808 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 5/8 tasks completed.
2024-08-14 07:20:58.810 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 6/8 tasks completed.
2024-08-14 07:20:58.812 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 7/8 tasks completed.
2024-08-14 07:21:08.399 | SUCCESS  | datatrove.executor.base:_run_for_rank:85 - Processing done for rank=0
2024-08-14 07:21:08.401 | INFO     | datatrove.executor.base:_run_for_rank:91 -

📉📉📉 Stats: Task 0 📉📉📉

Total Runtime: 9 seconds

📖 - READER: 🐿 Jsonl
    Runtime: (1.54%) 0 seconds [0.03 milliseconds±0.01 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc], documents: 5727 [5727.00/input_file]}
🔢 - TOKENIZER: 📊 Counter
    Runtime: (79.15%) 7 seconds [1.29 milliseconds±5.90 milliseconds/doc]
    Stats: {tokens: 3989039 [min=54, max=18060, 696.41±1020/doc]}
🫂 - DEDUP: 🎯 MinHash stage 4
    Runtime: (0.44%) 0 seconds [0.01 milliseconds±0.03 milliseconds/doc]
    Stats: {total: 5728, forwarded: 5548, dropped: 180}
💽 - WRITER: 🐿 Jsonl
    Runtime: (18.86%) 1 second [0.32 milliseconds±0.44 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 5548, total: 5548, doc_len: 17896157 [min=257, max=73080, 3225.70±4665/doc], doc_len_tokens: 3943328 [min=54, max=18060, 710.77±1032/doc]}
2024-08-14 07:21:08.405 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 8/8 tasks completed.
2024-08-14 07:21:08.417 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 8 tasks 📉📉📉

Total Runtime: 1 second ± 2 seconds/task

📖 - READER: 🐿 Jsonl
    Runtime: (1.54%) 0 seconds±0 seconds/task, min=0 seconds [0.03 milliseconds±0.01 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc], documents: 5727 [5727.00/input_file]}
🔢 - TOKENIZER: 📊 Counter
    Runtime: (79.15%) 0 seconds±2 seconds/task, min=0 seconds [1.29 milliseconds±5.90 milliseconds/doc]
    Stats: {tokens: 3989039 [min=54, max=18060, 696.41±1020/doc]}
🫂 - DEDUP: 🎯 MinHash stage 4
    Runtime: (0.44%) 0 seconds±0 seconds/task, min=0 seconds [0.01 milliseconds±0.03 milliseconds/doc]
    Stats: {total: 5728, forwarded: 5548, dropped: 180}
💽 - WRITER: 🐿 Jsonl
    Runtime: (18.86%) 0 seconds±0 seconds/task, min=0 seconds [0.32 milliseconds±0.44 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 5548, total: 5548, doc_len: 17896157 [min=257, max=73080, 3225.70±4665/doc], doc_len_tokens: 3943328 [min=54, max=18060, 710.77±1032/doc]}
```
### Check removed and final result in this part:
```
(dataclean) root@david1a100:~/dataclean/minhash# ls -al removed/
total 76
drwx------ 2 root root  4096 Aug 14 07:20 .
drwx------ 7 root root  4096 Aug 14 07:20 ..
-rw------- 1 root root 65584 Aug 14 07:21 00000.jsonl.gz
(dataclean) root@david1a100:~/dataclean/minhash# ls -al deduplicated_output/
total 7372
drwx------ 2 root root    4096 Aug 14 07:20 .
drwx------ 7 root root    4096 Aug 14 07:20 ..
-rw------- 1 root root 7539420 Aug 14 07:21 00000.jsonl.gz
(dataclean) root@david1a100:~/dataclean/minhash#
```
Check first intem in final output file:
```
(dataclean) root@david1a100:~/dataclean/minhash/deduplicated_output# zcat ./00000.jsonl.gz | head -n 1 | jq .
{
  "text": "Buy Ambien Online Legally (Zolpidem) belongs to the imidazopyridines class of opioids. Ambien complements the exceptional of sleep via way of means of decreasing the time it takes to fall asleep, decreasing the frequency of nocturnal awakenings, and growing the general period of sleep. Lengthens the second one degree of sleep and the deep sleep degree (III and IV). It does now no longer make you sleepy throughout the day. If you’re seeking to Buy Ambien Online at an inexpensive cost, come to our on line pharmacy.",
  "id": "<urn:uuid:dd20979b-ada8-4c5b-b53e-4ade7274bc1b>",
  "metadata": {
    "dump": "CC-MAIN-2023-23",
    "url": "http://42627.dynamicboard.de/u101117_ambienusa.html",
    "date": "2023-05-27T23:12:51Z",
    "file_path": "/root/dataclean/data/CC-MAIN-2023-23/segments/CC-MAIN-20230527223515-20230528013515-00000.warc.gz",
    "language": "en",
    "language_score": 0.8990675806999207,
    "token_count": 120
  }
}
```

## Sentence deduplication

My code uses the local executor `LocalPipelineExecutor` to execute the data deduplication pipeline, which includes the following steps:

- **Configuring Sentence Deduplication**: Setting up sentence deduplication with specific configurations such as the number of sentences, splitting sentences, and minimum document words.

- **Preprocessing Data**: Using NLTK to download the Punkt tokenizer and preprocess data before starting multiprocessing.

- **Reading Input Data**: Using `JsonlReader` to read input data from a specified directory.

- Stage 1: Extracting and Filtering Content:

  - **Pipeline**: Reads input data, extracts content using Trafilatura, filters based on quality and language, and writes intermediate results to JSONL files.
  - **Output**: Stores intermediate results in a specified folder.
  - **Tasks**: Configured to run with a specified number of tasks.

- Stage 2: Calculating Sentence Deduplication Signatures:

  - **Pipeline**: Processes the intermediate results to calculate sentence deduplication signatures.
  - **Output**: Stores signatures in a specified folder.
  - **Tasks**: Runs with a number of tasks equal to the number of finder workers.

- Stage 3: Finding and Filtering Duplicates:

  - **Pipeline**: Reads the intermediate results, finds duplicates using the calculated signatures, and filters out duplicates (keeping only one sample per cluster).

  - **Output**: Stores deduplicated output in a specified folder.

  - **Tasks**: Configured to run with a specified number of tasks.

    The pipeline is executed by running `executor_1.run()`, `executor_2.run()`, and `executor_3.run()`.

```
(dataclean) root@david1a100:~/dataclean# cat sentence_deduplication.py
```
```
import nltk
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
from datatrove.executor.base import PipelineExecutor
from datatrove.executor.local import LocalPipelineExecutor
from datatrove.pipeline.dedup import SentenceDedupFilter, SentenceDedupSignature, SentenceFindDedups
from datatrove.pipeline.dedup.sentence_dedup import SentDedupConfig
from datatrove.pipeline.extractors import Trafilatura
from datatrove.pipeline.filters import GopherQualityFilter, LanguageFilter
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.writers.jsonl import JsonlWriter
from datatrove.utils.typeshelper import Languages
from datatrove.io import get_datafolder
from collections import UserDict
import multiprocessing

# Ensure punkt tokenizer is downloaded before multiprocessing
nltk.download('punkt', force=True)

# Custom function to load PunktSentenceTokenizer
def load_punkt_tokenizer():
    punkt_param = PunktParameters()
    with open(nltk.data.find('tokenizers/punkt/english.pickle'), 'rb') as f:
        tokenizer = PunktSentenceTokenizer(punkt_param)
    return tokenizer

# Load tokenizer in the main process
tokenizer = load_punkt_tokenizer()

# Example configuration for sentence deduplication
sent_dedup_config = SentDedupConfig(
    n_sentences=3,
    split_sentences=True,
    only_dedup_in_index=True,
    min_doc_words=50,
)

FINDER_WORKERS = 10

class TimeStats:
    def __init__(self):
        self.global_mean = 0
        self.global_std_dev = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __repr__(self):
        return f"TimeStats(global_mean={self.global_mean}, global_std_dev={self.global_std_dev})"

    def __add__(self, other):
        result = TimeStats()
        result.global_mean = self.global_mean + other.global_mean
        result.global_std_dev = self.global_std_dev + other.global_std_dev
        return result

class Stat:
    def __init__(self):
        self.value = 0

    def update(self, value, unit=None):
        self.value += value

    def __repr__(self):
        return f"Stat(value={self.value})"

    def __add__(self, other):
        result = Stat()
        result.value = self.value + other.value
        return result

class PipelineStats(UserDict):
    def __init__(self):
        super().__init__()
        self.total_runtime = 0
        self.time_stats = TimeStats()
        self.data['total'] = Stat()
        self.data['removed_sentences'] = Stat()
        self.data['original_sentences'] = Stat()

    def as_dict(self):
        return {
            'total_runtime': self.total_runtime,
            'time_stats': repr(self.time_stats),
            'stats': {key: repr(value) for key, value in self.data.items()}
        }

    def to_dict(self):
        return self.as_dict()

    def to_json(self):
        import json
        return json.dumps(self.to_dict(), indent=4)

    def save_to_disk(self, file):
        file.write(self.to_json())

    def get_repr(self, task_name):
        x = f"\n\n📉📉📉 Stats: {task_name} 📉📉📉\n\nTotal Runtime: {self.total_runtime} seconds\n\n"
        x += "\n".join([repr(stat) for stat in self.data.values()])
        return x

    def __repr__(self, *args, **kwargs):
        return f"PipelineStats(total_runtime={self.total_runtime}, time_stats={self.time_stats})"

    def __add__(self, other):
        result = PipelineStats()
        result.total_runtime = self.total_runtime + other.total_runtime
        result.time_stats = self.time_stats + other.time_stats
        for key in self.data:
            result.data[key] = self.data[key] + other.data[key]
        return result

class CustomSentenceDedupFilter(SentenceDedupFilter):
    def __init__(self, data_folder, config):
        self.data_folder = get_datafolder(data_folder)
        self.config = config
        self._tokenizer = None
        self.exclusion_writer = None
        self.stats = PipelineStats()
        self.language = 'english'

    def set_tokenizer(self, tokenizer):
        self._tokenizer = tokenizer

    def run(self, data, rank, world_size, *args):
        # Implement the logic for the run method here
        # For now, let's just print the arguments to verify they are passed correctly
        print(f"Running with data: {data}, rank: {rank}, world_size: {world_size}, args: {args}")
        # Add your actual processing logic here
        return data

def preprocess_data():
    # Preprocess data using nltk before starting multiprocessing
    # This is a placeholder function. Implement your preprocessing logic here.
    # For example, you can read the input files, tokenize the sentences, and save the preprocessed data.
    pass

def run_example():
    preprocess_data()  # Preprocess data before starting multiprocessing

    pipeline_1 = [
        JsonlReader(data_folder="./minhash/deduplicated_output/"),
        Trafilatura(),
        GopherQualityFilter(min_stop_words=0),
        LanguageFilter(language_threshold=0.5, languages=(Languages.english,)),
        JsonlWriter("./intermediate/"),
        SentenceDedupSignature(output_folder="./c4/sigs", config=sent_dedup_config, finder_workers=FINDER_WORKERS),
    ]

    pipeline_2 = [SentenceFindDedups(data_folder="./c4/sigs", output_folder="./c4/dups", config=sent_dedup_config)]

    sentence_dedup_filter = CustomSentenceDedupFilter(data_folder="./c4/dups", config=sent_dedup_config)
    sentence_dedup_filter.set_tokenizer(tokenizer)

    pipeline_3 = [
        JsonlReader(data_folder="./intermediate/"),
        sentence_dedup_filter,
        JsonlWriter(output_folder="./final_deduplicated_output/"),
    ]

    executor_1: PipelineExecutor = LocalPipelineExecutor(pipeline=pipeline_1, workers=4, tasks=4)
    executor_2: PipelineExecutor = LocalPipelineExecutor(pipeline=pipeline_2, workers=1, tasks=FINDER_WORKERS)
    executor_3: PipelineExecutor = LocalPipelineExecutor(pipeline=pipeline_3, workers=4, tasks=4)

    print(executor_1.run())
    print(executor_2.run())
    print(executor_3.run())

if __name__ == '__main__':
    multiprocessing.freeze_support()
    run_example()
```
Run the script:
```
(dataclean) root@david1a100:~/dataclean# python3 sentence_deduplication.py
```
Some of the output:
```
2024-08-15 03:46:20.151 | INFO     | datatrove.pipeline.dedup.sentence_dedup:run:247 - PQ initialized.
2024-08-15 03:46:20.151 | SUCCESS  | datatrove.executor.base:_run_for_rank:85 - Processing done for rank=9
2024-08-15 03:46:20.152 | INFO     | datatrove.executor.base:_run_for_rank:91 -

📉📉📉 Stats: Task 9 📉📉📉

Total Runtime: 0 seconds

🫂 - DEDUPS: 💥 sentence-deduplication stage 2
    Runtime: (100.00%) 0 seconds [1.17 milliseconds±0 milliseconds/doc]
2024-08-15 03:46:20.156 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 10 tasks 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

🫂 - DEDUPS: 💥 sentence-deduplication stage 2
    Runtime: (100.00%) 0 seconds±0 seconds/task, min=0 seconds, max=0 seconds [1.68 milliseconds±1.21 milliseconds/doc]


📉📉📉 Stats 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

🫂 - DEDUPS: 💥 sentence-deduplication stage 2
    Runtime: (100.00%) 0 seconds±0 seconds/task, min=0 seconds, max=0 seconds [1.68 milliseconds±1.21 milliseconds/doc]
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data]   Unzipping tokenizers/punkt.zip.
[nltk_data]   Unzipping tokenizers/punkt.zip.
[nltk_data]   Unzipping tokenizers/punkt.zip.
[nltk_data]   Unzipping tokenizers/punkt.zip.
2024-08-15 03:46:20.887 | INFO     | datatrove.utils.logging:add_task_logger:47 - Launching pipeline for rank=2
2024-08-15 03:46:20.887 | INFO     | datatrove.utils.logging:log_pipeline:76 -
--- 🛠️ PIPELINE 🛠
📖 - READER: 🐿 Jsonl
🫂 - DEDUPS: 💥 sentence-deduplication stage 3
💽 - WRITER: 🐿 Jsonl
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a030>, rank: 2, world_size: 4, args: ()
2024-08-15 03:46:20.887 | WARNING  | datatrove.pipeline.readers.base:run:226 - No files found on /root/dataclean/intermediate for rank=2
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a030>, rank: 1, world_size: 4, args: ()
2024-08-15 03:46:20.887 | SUCCESS  | datatrove.executor.base:_run_for_rank:85 - Processing done for rank=2
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a030>, rank: 0, world_size: 4, args: ()
2024-08-15 03:46:20.888 | INFO     | datatrove.executor.base:_run_for_rank:91 -

📉📉📉 Stats: Task 2 📉📉📉

Total Runtime: 0 seconds

📖 - READER: 🐿 Jsonl
PipelineStats(total_runtime=0, time_stats=TimeStats(global_mean=0, global_std_dev=0))
💽 - WRITER: 🐿 Jsonl
2024-08-15 03:46:20.891 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 1/4 tasks completed.
2024-08-15 03:46:20.892 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 2/4 tasks completed.
2024-08-15 03:46:20.897 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 3/4 tasks completed.
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a340>, rank: 3, world_size: 4, args: ()
2024-08-15 03:46:20.911 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 4/4 tasks completed.
2024-08-15 03:46:20.948 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 4 tasks 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

📖 - READER: 🐿 Jsonl
    Runtime: (7.77%) 0 seconds±0 seconds/task, min=0 seconds [0.06 milliseconds±0.04 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc], documents: 3 [3.00/input_file]}
PipelineStats(total_runtime=0, time_stats=TimeStats(global_mean=0, global_std_dev=0))
💽 - WRITER: 🐿 Jsonl
    Runtime: (92.23%) 0 seconds±0 seconds/task, min=0 seconds [0.66 milliseconds±0.88 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 4, total: 4, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc]}


📉📉📉 Stats 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

📖 - READER: 🐿 Jsonl
    Runtime: (7.77%) 0 seconds±0 seconds/task, min=0 seconds [0.06 milliseconds±0.04 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc], documents: 3 [3.00/input_file]}
PipelineStats(total_runtime=0, time_stats=TimeStats(global_mean=0, global_std_dev=0))
💽 - WRITER: 🐿 Jsonl
    Runtime: (92.23%) 0 seconds±0 seconds/task, min=0 seconds [0.66 milliseconds±0.88 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 4, total: 4, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc]}
```
Check the the first item of final outputs:

```
(dataclean) root@david1a100:~/dataclean/final_deduplicated_output#  zcat ./00000.jsonl.gz | head -n 1 | jq .
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Make-High-Quality-Dataset-From-WARC/images/2.png)


# Check quality of the corpus

This part of my code is refer to: https://github.com/Azure/synthetic-qa-generation/tree/main*, I modified some codes, please refer to corpus-suggestions.ipynb, which could analyze quality of the corpus from the last steps and give lots of useful suggestions.

Take some results as examples:
```
Result 1:
Feedback Required: [True, False, True, False, True]
Feedback List:
#Need Feedback#: Yes
#Issue Name#: Lack of new scenarios or contexts
#Reason#: The evolved instruction does not introduce any new scenarios or examples.
#Feedback#: Introduce diverse contexts or examples to enhance the instructional variety.
#Need Feedback#: No
#Need Feedback#: Yes
#Issue Name#: Limited diversity in examples
#Reason#: No new scenarios or varied contexts introduced in the evolved instruction.
#Feedback#: Incorporate diverse examples or contexts to cover a wider range of situations.
#Need Feedback#: No
#Need Feedback#: Yes
#Issue Name#: Limited diversity
#Reason#: No new scenarios, examples, or contexts introduced.
#Feedback#: Include various use cases and contexts for accessing journal content.
Optimized Instruction:
Accessing full-text articles for free on HTML pages can be a convenient way to stay informed, but if you need the article in PDF or Epub format, a subscription to the Journal of Postgraduate Medicine is required. Here are different ways to access the content based on various contexts:

1. **Individual Subscription:** If you frequently need access to articles in PDF or Epub format, consider subscribing online for a year. Subscribing is a straightforward process:

   - Visit the Journal of Postgraduate Medicine's subscription page.
   - Choose the subscription plan that suits your needs.
   - Complete the payment process to gain access to the content.

2. **Institutional Access:** If you are affiliated with a university or a research institution, you might recommend that your institution's library subscribe to the journal. This way, everyone at your institution can have unrestricted access to the content.

   - Click on the "Recommend the Journal" link typically provided on the journal's website.
   - Fill out the recommendation form with the necessary details.
   - Submit the recommendation to your institution's library acquisition team.

3. **Library Access:** If your local library has a subscription to the journal, you can access the PDF and Epub formats through their facilities. Check with your library to see if they offer remote access options, especially useful during non-operational hours or remote working conditions.

4. **Interlibrary Loan (ILL):** If neither you nor your institution has a subscription and you need a specific article in PDF or Epub format, you can request it through interlibrary loan services:

   - Contact your library's interlibrary loan department.
   - Provide the details of the article you need.
   - Wait for your library to obtain a copy from another subscribing institution.

5. **Pay-Per-View Purchase:** Some journals offer pay-per-view options for non-subscribers to access specific articles:

   - Visit the article page on the journal's website.
   - Look for a purchase or pay-per-view option.
   - Complete the payment to download the article in PDF or Epub format.

By understanding these various methods, you can choose the most appropriate way to access the Journal of Postgraduate Medicine articles based on your specific context and needs.
Evolved Instruction Step 1:
Accessing full-text articles for free on HTML pages can be a convenient way to stay informed, but if you need the article in PDF or Epub format or face geographic restrictions, a subscription to the Journal of Postgraduate Medicine is required. Here are different ways to access the content based on various contexts and considerations:

1. **Individual Subscription:** If you frequently need access to articles in PDF or Epub format, consider subscribing online for a year. Consider different subscription tiers based on your usage frequency and preferred payment method (credit card, PayPal, or wire transfer):

   - Visit the Journal of Postgraduate Medicine's subscription page.
   - Choose the appropriate subscription plan that suits your reading needs and budget.
   - Complete the payment process, selecting your preferred payment method, to gain access to the content.
   - Confirm your subscription through the verification email you will receive.

2. **Institutional Access:** If you are affiliated with a university, specialized institute, or research organization, you might recommend that your institution's library subscribe to the journal, allowing everyone at your institution unrestricted access to the content:

   - Click on the "Recommend the Journal" link typically provided on the journal's website.
   - Fill out the recommendation form with the necessary details, specifying your institution type.
   - Submit the recommendation to your institution's library acquisition team.
   - Follow up with your acquisition team to verify the status of the subscription request.

3. **Library Access:** If your local library has a subscription to the journal, you can access the PDF and Epub formats through their facilities. Check with your library to see if they offer remote access options or have updated policies for off-hour access due to remote working conditions or geographical restrictions:

   - Visit your library's online resource portal.
   - Authenticate your library membership details to access the journal remotely.
   - Verify the access duration and loan policies to ensure continuous availability.

4. **Interlibrary Loan (ILL):** If neither you nor your institution has a subscription and you need a specific article in PDF or Epub format, you can request it through Interlibrary Loan services, which might involve multiple steps and waiting periods:

   - Contact your library's interlibrary loan department and inquire about any pre-requisites.
   - Provide the exact details of the article you need and verify your contact information.
   - Wait for your library to notify you on the progress and estimated delivery time of the article from another subscribing institution.
   - Confirm the received article's access duration to avoid lapses in availability.

5. **Pay-Per-View Purchase:** Some journals offer pay-per-view options for non-subscribers to access specific articles. Be aware of different payment methods and possible return policies if the article does not meet your needs:

   - Visit the article page on the journal's website.
   - Look for a purchase or pay-per-view option and compare prices if there are multiple.
   - Complete the payment process, choosing a method that's secure and convenient for you.
   - Download the article in PDF or Epub format, and review any return policies if you face access issues.

By understanding these various methods, including conditional scenarios and additional steps, you can choose the most appropriate way to access the Journal of Postgraduate Medicine articles based on your specific context, requirements, and potential contingent situations.
New Feedback Required: [True, True, True, True, True]
New Feedback List:
#Need Feedback#: Yes
    #Issue Name#: Preservation of key information
    #Reason#: Key information is maintained with added details and considerations.
    #Feedback#: Key information preserved well with added context and steps for clarity.
#Need Feedback#: Yes
#Issue Name#: Complexity
#Reason#: More details and steps have been added sufficiently.
#Feedback#: Complexity increased adequately with detailed steps and additional considerations.
#Need Feedback#: Yes
#Issue Name#: Insufficient scenario diversity
#Reason#: Limited expansion on new contexts or examples in evolved instruction.
#Feedback#: Introduce more varied scenarios to enhance diversity and coverage of different situations.
#Need Feedback#: Yes
#Issue Name#: Increased complexity
#Reason#: The Evolved Instruction introduces more detailed steps and additional considerations.
#Feedback#: The complexity has increased adequately with additional steps and detailed guidance.
#Need Feedback#: Yes
    #Issue Name#: Limited diversity in access methods
    #Reason#: Few new scenarios or examples introduced in the evolved instruction.
    #Feedback#: Expand diversity by adding varied contexts, like international access options.
```

## Genarate Synthetic Q&A 

Refer to generate-QA.ipynb, we could generate high quality synthetic Q&A pairs with GPT -4o. Prompt temlpate is refer to : *https://github.com/Azure/synthetic-qa-generation/tree/main/seed/prompt_template/en*
Take some results as examples:
```
1. **What type of access is free in HTML pages?**
   Full text access is free in HTML pages.

2. **Who can access PDF and EPub formats of the journal?**
   PDF and EPub access is only available to paid subscribers and members.

3. **What must you do to access the article in PDF format?**
   To access the article in PDF format, you should be a subscriber to the Journal of Postgraduate Medicine.

4. **How can you subscribe to the Journal of Postgraduate Medicine?**
   You can subscribe online for a year.

5. **What can you do if you want your institution to have unrestricted access to the journal?**
   You could recommend your institution's library to subscribe to the journal so that you can have unrestricted access.
```


## References
- DataTrove: https://github.com/huggingface/datatrove/
- Generate Synthetic QnAs from Real-world Data: https://github.com/Azure/synthetic-qa-generation/

