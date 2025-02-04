import logging
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from settings import MILVUS_HOST, MILVUS_PORT, VECTOR_DIMENSION
import re
import jieba
import time

logger = logging.getLogger(__name__)

class MilvusStore:
    def __init__(self):
        try:
            logger.info(f"连接Milvus服务器: {MILVUS_HOST}:{MILVUS_PORT}")
            self.conn = connections.connect(
                host=MILVUS_HOST,
                port=MILVUS_PORT
            )
            self.col = None
            logger.info("Milvus连接成功")
        except Exception as e:
            logger.error(f"连接Milvus服务器失败: {str(e)}")
            raise

    def create_collection(self, collection_name):
        try:
            logger.info(f"开始创建集合: {collection_name}")
            
            if utility.has_collection(collection_name):
                logger.info(f"集合 {collection_name} 已存在，正在删除")
                collection = Collection(collection_name)
                collection.drop()
                # 等待删除操作完成
                for _ in range(30):
                    if not utility.has_collection(collection_name):
                        break
                    time.sleep(1)
                if utility.has_collection(collection_name):
                    raise Exception("删除集合超时")
                logger.info("旧集合删除成功")
            
            # 保持原有字段和schema定义
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65000),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIMENSION),
                FieldSchema(name="version", dtype=DataType.VARCHAR, max_length=10),
                FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=1024),
                FieldSchema(name="is_community", dtype=DataType.BOOL)
            ]
            
            schema = CollectionSchema(fields=fields, description=f"Collection for {collection_name}")
            collection = Collection(name=collection_name, schema=schema)
            
            # 创建索引
            index_params = {
                "metric_type": "IP",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            collection.create_index(field_name="vector", index_params=index_params)
            utility.wait_for_index_building_complete(collection_name)
            
            return collection
            
        except Exception as e:
            logger.error(f"创建集合失败: {str(e)}")
            raise

    def _find_best_split_point(self, text, max_length):
        """找到最佳分割点，优先考虑段落、句子和词语边界"""
        if len(text) <= max_length:
            return len(text)
        
        # 在max_length范围内寻找最佳分割点
        text_to_search = text[:max_length]
        
        # 1. 优先在段落处分割
        paragraph_splits = text_to_search.rfind('\n\n')
        if paragraph_splits != -1 and paragraph_splits > max_length * 0.5:
            return paragraph_splits
        
        # 2. 其次在句子边界分割
        sentence_endings = [m.end() for m in re.finditer('[。！？\n]', text_to_search)]
        if sentence_endings and sentence_endings[-1] > max_length * 0.5:
            return sentence_endings[-1]
        
        # 3. 最后在词语边界分割
        words = list(jieba.cut(text_to_search))
        current_length = 0
        for i, word in enumerate(words):
            current_length += len(word)
            if current_length > max_length * 0.8:
                return sum(len(w) for w in words[:i])
        
        # 如果没有找到合适的分割点，强制分割
        return max_length

    def _split_text(self, text, max_length=63000):
        """递归的文本分割算法"""
        def recursive_split(text_chunk):
            if len(text_chunk) <= max_length:
                return [text_chunk]
            
            # 在max_length范围内找到最佳分割点
            split_point = self._find_best_split_point(text_chunk, max_length)
            first_chunk = text_chunk[:split_point].strip()
            remaining_chunk = text_chunk[split_point:].strip()
            
            # 递归处理两个部分
            result = []
            if first_chunk:
                # 递归检查第一部分是否需要继续分割
                if len(first_chunk) > max_length:
                    logger.warning(f"第一部分仍然超长: {len(first_chunk)}，继续分割")
                    result.extend(recursive_split(first_chunk))
                else:
                    result.append(first_chunk)
            
            if remaining_chunk:
                # 递归检查剩余部分是否需要继续分割
                if len(remaining_chunk) > max_length:
                    logger.warning(f"剩余部分超长: {len(remaining_chunk)}，继续分割")
                    result.extend(recursive_split(remaining_chunk))
                else:
                    result.append(remaining_chunk)
            
            return result

        # 开始分割
        if len(text) <= max_length:
            return [text]
        
        logger.warning(f"发现超长文本: {len(text)}，进行预处理分割")
        chunks = recursive_split(text)
        
        # 最终检查所有片段
        final_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_len = len(chunk)
            if chunk_len > max_length:
                logger.error(f"片段 {i} 仍然超长: {chunk_len} > {max_length}")
                logger.error(f"文本预览:\n{chunk[:200]}...\n...{chunk[-200:]}")
                # 强制截断
                chunk = chunk[:max_length]
                logger.warning(f"强制截断为 {len(chunk)} 字符")
            final_chunks.append(chunk)
        
        logger.info(f"文本长度 {len(text)} 被分割成 {len(final_chunks)} 个片段")
        for i, chunk in enumerate(final_chunks):
            logger.info(f"片段 {i} 长度: {len(chunk)}")
        
        return final_chunks

    def _create_chunk_metadata(self, original_id, chunks):
        """为文本片段创建元数据"""
        chunk_metadata = []
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks):
            metadata = {
                "doc_id": original_id,
                "chunk_id": i,
                "total_chunks": total_chunks,
                "prev_chunk_id": i - 1 if i > 0 else -1,
                "next_chunk_id": i + 1 if i < total_chunks - 1 else -1
            }
            chunk_metadata.append(metadata)
        
        return chunk_metadata

    def _clean_text(self, text):
        """清理文本内容，去除 License 等无关信息"""
        # 移除 YAML front matter
        if text.startswith('---'):
            parts = text.split('---', 2)
            if len(parts) >= 3:
                text = parts[2]
        
        # 移除 License 头部
        license_end = text.find('*/') # 找到注释结束位置
        if license_end != -1 and 'Licensed to the Apache Software Foundation' in text[:license_end]:
            text = text[license_end + 2:].strip()
        
        # 移除多余的空行
        text = '\n'.join(line for line in text.splitlines() if line.strip())
        return text

    def insert_data(self, collection_name, data, batch_size=200):
        """改进的数据插入方法"""
        logger.info(f"开始向集合 {collection_name} 插入数据，数据量: {len(data)}")
        collection = Collection(collection_name)
        max_text_length = 63000
        
        processed_data = []
        current_id = 0
        failed_items = []  # 记录插入失败的数据
        
        # 处理所有数据
        for i, item in enumerate(data):
            try:
                # 清理文本内容
                cleaned_text = self._clean_text(item["text"])
                item["text"] = cleaned_text
                
                # 检查原始文本长度
                if len(item["text"]) > max_text_length:
                    text_chunks = self._split_text(item["text"])
                    if len(text_chunks) > 1:
                        logger.info(f"文档 {i} 被分割成 {len(text_chunks)} 个片段")
                else:
                    text_chunks = [item["text"]]
                
                chunk_metadata = self._create_chunk_metadata(i, text_chunks)
                
                # 创建每个片段的记录
                for j, (chunk, metadata) in enumerate(zip(text_chunks, chunk_metadata)):
                    processed_item = item.copy()
                    processed_item["id"] = current_id
                    processed_item["text"] = chunk
                    processed_item.update(metadata)
                    processed_item["has_more"] = j < len(text_chunks) - 1
                    processed_item["sequence"] = j
                    
                    if len(text_chunks) > 1:
                        processed_item["url"] = f"{item['url']}#part{metadata['chunk_id']+1}"
                    
                    processed_data.append(processed_item)
                    current_id += 1
            except Exception as e:
                logger.error(f"处理文档 {i} 时发生错误: {str(e)}")
                failed_items.append({"index": i, "url": item.get("url", "unknown"), "error": str(e)})
                continue
        
        total_chunks = len(processed_data)
        logger.info(f"处理后的总记录数: {total_chunks}")
        
        # 分批插入处理后的数据
        successful_inserts = 0
        for i in range(0, total_chunks, batch_size):
            batch = processed_data[i:i + batch_size]
            logger.info(f"插入第 {i//batch_size + 1} 批数据，范围: {i}-{min(i + batch_size, total_chunks)}")
            
            # 逐条插入数据
            successful_batch = []
            for idx, item in enumerate(batch):
                try:
                    # 检查文本长度
                    text_len = len(item["text"])
                    if text_len > 63000:
                        logger.error(f"发现异常超长文本: {text_len} > 63000")
                        logger.error(f"文档URL: {item.get('url', 'unknown')}")
                        logger.error(f"文本内容预览:\n{item['text'][:200]}...\n...{item['text'][-200:]}")
                        failed_items.append({
                            "index": idx + i,
                            "url": item.get("url", "unknown"),
                            "length": text_len,
                            "error": "文本超长"
                        })
                        continue
                    
                    # 插入单条数据
                    collection.insert([item])
                    successful_batch.append(item)
                    successful_inserts += 1
                    
                except Exception as e:
                    logger.error(f"插入第 {idx + i} 条数据时发生错误: {str(e)}")
                    failed_items.append({
                        "index": idx + i,
                        "url": item.get("url", "unknown"),
                        "error": str(e)
                    })
            
            # 批量持久化成功插入的数据
            if successful_batch:
                try:
                    logger.info("等待数据持久化...")
                    collection.flush()
                    res = utility.wait_for_index_building_complete(collection_name)
                    if not res:
                        logger.error(f"批次 {i//batch_size + 1} 数据持久化超时")
                    else:
                        logger.info(f"成功持久化第 {i//batch_size + 1} 批数据中的 {len(successful_batch)} 条记录")
                    
                    # 验证插入
                    time.sleep(1)
                    count = collection.num_entities
                    logger.info(f"当前集合实体数量: {count}")
                    
                except Exception as e:
                    logger.error(f"持久化第 {i//batch_size + 1} 批数据时发生错误: {str(e)}")
        
        # 汇总处理结果
        logger.info(f"数据插入完成，成功: {successful_inserts}，失败: {len(failed_items)}")
        if failed_items:
            logger.error("失败项目详情:")
            for item in failed_items:
                logger.error(f"索引: {item['index']}, URL: {item['url']}, 错误: {item['error']}")
        
        return successful_inserts > 0  # 只要有成功插入的数据就返回True
        
    def search(self, collection_name, query_vector, limit=5):
        """改进版搜索，增加多样性"""
        try:
            if not self.col or self.col.name != collection_name:
                self.col = Collection(collection_name)
                self.col.load()
            
            # 使用混合搜索参数
            search_params = {
                "metric_type": "IP",
                "params": {
                    "nprobe": 32,  # 增加搜索范围
                    "radius": 0.7   # 控制结果多样性
                }
            }
            
            # 添加版本过滤（优先3.0和2.1）
            expr = "version in ['3.0', '2.1']"  # 优先最新版本
            
            results = self.col.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=limit*3,  # 扩大初始结果集
                expr=expr,
                output_fields=["text", "version", "url", "is_community"]
            )
            
            logger.info(f"搜索完成，找到 {len(results[0])} 条结果")
            
            # 处理搜索结果
            results_with_context = []
            for hits in results:  # results[0] 是第一个查询的结果
                for hit in hits:  # 遍历每个匹配项
                    entity = hit.entity
                    doc_data = {
                        "text": str(entity.text) if hasattr(entity, 'text') else "",
                        "version": str(entity.version) if hasattr(entity, 'version') else "",
                        "url": str(entity.url) if hasattr(entity, 'url') else "",
                        "is_community": bool(entity.is_community) if hasattr(entity, 'is_community') else False,
                        "score": float(hit.score)
                    }
                    results_with_context.append(doc_data)
            
            return results_with_context
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            raise

    def insert(self, collection_name, data):
        """插入数据到集合，支持批量或单条插入"""
        try:
            if not data:
                return 0
            
            # 统一处理为列表格式
            if not isinstance(data, list):
                data = [data]
            
            # 转换数据格式
            entities = []
            for item in data:
                try:
                    entities.append({
                        "id": str(item["id"]),
                        "text": str(item["text"])[:65000],  # 强制类型转换和长度限制
                        "vector": [float(x) for x in item["vector"]],
                        "version": str(item["version"]),
                        "url": str(item["url"]),
                        "is_community": bool(item["is_community"])
                    })
                except Exception as e:
                    logger.error(f"数据转换失败: {str(e)} | 原始数据: {item}")
                    continue
            
            if not entities:
                logger.warning("无有效数据可插入")
                return 0
            
            # 转换为列格式
            columns = [
                [entity["id"] for entity in entities],
                [entity["text"] for entity in entities],
                [entity["vector"] for entity in entities],
                [entity["version"] for entity in entities],
                [entity["url"] for entity in entities],
                [entity["is_community"] for entity in entities]
            ]
            
            # 获取集合对象
            collection = Collection(name=collection_name)
            # 执行插入
            result = collection.insert(columns)
            logger.info(f"成功插入 {len(entities)} 条数据到 {collection_name}")
            return len(entities)
            
        except Exception as e:
            logger.error(f"数据插入失败: {str(e)}")
            raise 