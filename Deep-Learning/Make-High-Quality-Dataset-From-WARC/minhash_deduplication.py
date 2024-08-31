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
    # 配置Minhash  
    minhash_config = MinhashConfig(use_64bit_hashes=True)  # 更好的精度 -> 更少的误报（碰撞）  
  
    # 本地路径配置  
    LOCAL_MINHASH_BASE_PATH = "./minhash"  
    LOCAL_LOGS_FOLDER = "./logs"  
    TOTAL_TASKS = 8  # 根据你的本地环境调整任务数量  
  
    # 输入数据路径  
    INPUT_READER = JsonlReader("./output/output/CC-MAIN-2023-23/")  
  
    # 阶段1：计算每个任务的Minhash签名  
    stage1 = LocalPipelineExecutor(  
        pipeline=[  
            INPUT_READER,  
            MinhashDedupSignature(output_folder=f"{LOCAL_MINHASH_BASE_PATH}/signatures", config=minhash_config),  
        ],  
        tasks=TOTAL_TASKS,  
        logging_dir=f"{LOCAL_LOGS_FOLDER}/signatures",  
    )  
  
    # 阶段2：在每个桶中查找签名之间的匹配  
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
  
    # 阶段3：使用所有桶的结果创建重复项的集群  
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
  
    # 阶段4：读取原始输入数据并删除每个重复集群中的所有样本（只保留一个）  
    stage4 = LocalPipelineExecutor(  
        pipeline=[  
            INPUT_READER,  
            TokensCounter(),  # 查看去重前后的token数量  
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
  
    # 运行管道  
    stage4.run()  
  
if __name__ == '__main__':  
    import multiprocessing  
    multiprocessing.freeze_support()  
    main()  

