import logging
from ..vectorstore.milvus_store import MilvusStore
import re
from settings import config
from src.moderation.moderation_service import ModerationService
from src.clients.llm_client import LLMClients
from concurrent.futures import ThreadPoolExecutor, TimeoutError

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        # 使用配置示例
        self.min_similarity = config.get_min_similarity
        self.version_weights = config.get_version_weights
        self.enable_keyword = config.get_enable_keyword
        
        self.config = config
        self.clients = LLMClients()
        self.milvus_store = MilvusStore()
        self.moderation_service = ModerationService()
        self.chat_model = config.get_chat_model
        logger.info("RAG引擎初始化成功")

    def _get_truncated_embedding(self, text):
        """处理文本截断并生成嵌入"""
        try:
            # 添加详细日志
            logger.debug(f"生成嵌入的文本长度: {len(text)}")
            logger.debug(f"使用模型: {self.config.embedding_model}")
            
            # 预处理文本，移除多余空白
            text = re.sub(r'\s+', ' ', text.strip())
            
            # 截断文本至8000字符（约对应8192 tokens）
            max_length = 8000
            if len(text) > max_length:
                logger.warning(f"文本长度超过限制，将截断至前{max_length}字符")
                text = text[:max_length]
            
            # 生成嵌入
            response = self.clients.embedding.embeddings.create(
                model=self.config.embedding_model,
                input=text,
                timeout=60.0  # 添加超时控制
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"嵌入生成失败详情: {str(e)}")
            logger.error(f"请求模型: {self.config.embedding_model}")
            logger.error(f"服务端点: {self.clients.embedding.base_url}")
            raise

    def get_embedding(self, text):
        """生成嵌入"""
        try:
            # 提取标题结构
            headings = []
            content_lines = []
            current_heading_level = 0
            
            for line in text.split('\n'):
                if line.startswith('#'):
                    level = line.count('#', 0, line.find(' '))
                    if level <= current_heading_level:  # 只保留最相关标题
                        headings = headings[:level-1]
                    headings.append(line.strip('#').strip())
                    current_heading_level = level
                else:
                    content_lines.append(line)
            
            # 构建关键文本
            key_text = f"文档结构：{' → '.join(headings)}\n核心内容：" + '\n'.join(content_lines[-300:])
            
            # 截断处理（保持与之前相同的逻辑）
            return self._get_truncated_embedding(key_text)
        
        except Exception as e:
            logger.error(f"嵌入生成失败: {str(e)}")
            raise
    
    def process_query(self, query: str, collection_name: str) -> str:
        """处理用户查询（带线程级超时控制）"""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._process_query, query, collection_name)
            try:
                return future.result(timeout=60)
            except TimeoutError:
                logger.error("查询处理超时")
                raise TimeoutError("请求超时")

    def _process_query(self, query: str, collection_name: str) -> str:
        """处理用户查询"""
        try:
            if not self.moderation_service.check_relevance(query):
                return "本服务仅支持Apache Doris相关咨询"
            
            # 原有处理逻辑保持不变
            logger.info("开始生成查询向量")
            query_vector = self.get_embedding(query)
            
            logger.info("开始检索相关文档")
            results = self.milvus_store.search(collection_name, query_vector, limit=3)
            
            # 打印搜索结果
            logger.info("搜索结果详情:")
            for i, res in enumerate(results):
                logger.info(f"\n文档 {i+1}:")
                logger.info(f"相关度分数: {res.get('score', 'N/A')}")
                logger.info(f"版本: {res.get('version', 'N/A')}")
                logger.info(f"URL: {res.get('url', 'N/A')}")
                logger.info(f"文本内容:\n{res.get('text', 'N/A')[:500]}...")
                logger.info("-" * 80)
            
            # 改进版结果处理
            def diversify_results(results):
                """多样性排序算法"""
                diversified = []
                seen_hashes = set()
                
                # 按版本优先级和内容相似度综合排序
                version_weights = {'3.0': 1.5, '2.1': 1.3, '2.0': 1.0, 'dev': 0.8}
                
                for res in results:
                    # 计算内容相似性哈希（取前500字符）
                    content_hash = hash(res['text'][:500])
                    
                    # 如果内容相似度超过80%，视为重复
                    if content_hash in seen_hashes:
                        continue
                    seen_hashes.add(content_hash)
                    
                    # 综合评分 = 相关度 * 版本权重
                    res['combined_score'] = res['score'] * version_weights.get(res.get('version', '2.0'), 1.0)
                    diversified.append(res)
                
                # 按综合评分排序
                return sorted(diversified, key=lambda x: x['combined_score'], reverse=True)[:3]
            
            # 应用多样性处理
            final_results = diversify_results(results)
            
            # 从最终结果中提取参考文档信息
            reference_docs = []
            for res in final_results:
                url = res.get('url', '')
                # 清理URL中的version-前缀
                clean_url = url.replace('version-', '')  # 兼容新旧格式
                # 从清理后的URL解析版本
                version = self._parse_version_from_url(clean_url)
                
                # 从URL锚点提取标题
                doc_title = "未命名文档"
                if '#' in url:
                    anchor = url.split('#')[-1]
                    doc_title = ' '.join(anchor.split('-')).title()  # 将短横线分隔转为空格
                
                reference_docs.append({
                    "version": version,
                    "title": doc_title,
                    "url": clean_url  # 使用清理后的URL
                })
            
            # 从搜索结果中提取文本作为上下文
            context = "\n".join([res["text"] for res in final_results])
            
            # 使用 DeepSeek 生成回答
            messages = [
                {"role": "system", "content": """你是一个专业的Apache Doris助手，你负责帮助用户解决技术问题。你可以访问产品文档，
                 其中包含有关 Doris 产品和服务的详细信息。你可以访问包含操作方法文章的内部知识库。你还可以访问用户经常寻求帮助的社区论坛。
                 你可以使用来自这些来源的信息来帮助用户解决他们的问题。除非你确定自己对用户的问题有准确的答案，
                 否则请提示用户将问题通过 https://ask.selectdb.com 论坛上报给社区人工支持同学，并告知用户你无法帮助他们。
                 如果你不确定，请不要编造答案。
                 我帮你查询到的参考文档和用户的输入如下。你的目标是尽最大努力帮助用户实现他们的目标。"""},
                {"role": "user", "content": f"""
                 参考文档:
                {context}
                用户问题: 
                {query}
                """}
            ]
            
            response = self.clients.chat.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=config.get_chat_temperature,
                max_tokens=800
            )
            
            # 生成带参考文档的回答
            response_content = response.choices[0].message.content
            formatted_response = f"{response_content}\n\n参考文档："
            for i, doc in enumerate(reference_docs, 1):
                formatted_response += f"\n{i}. 文档版本：{doc['version']} | {doc['title']} | {doc['url']}"
            
            return formatted_response
            
        except Exception as e:
            logger.error(f"查询处理失败: {str(e)}")
            raise

    def _parse_version_from_url(self, url):
        """更精确的版本解析"""
        if '/zh-CN/docs/' in url:
            path_parts = url.split('/zh-CN/docs/')[1].split('/')
            version_part = path_parts[0].replace('version-', '')
            if version_part == 'sql-manual':
                return '2.1' if '2.1' in url else 'unknown'
            return version_part if version_part in ['2.0','2.1','3.0','dev'] else 'unknown'
        return 'unknown'

    def _check_query_relevance(self, query):
        logger.info(f"开始审核问题: {query}")
        # 原始关键词审核逻辑
        keywords = ["doris", "数据库", "apache", "查询", "表", "分区", "分桶", "物化视图"]
        if any(kw in query.lower() for kw in keywords):
            logger.info(f"审核结果: 通过")
            return True
        
        # 原始深度审核逻辑
        try:
            messages = [
                {"role": "system", "content": "判断用户问题是否与Apache Doris数据库相关，仅回答Y/N"},
                {"role": "user", "content": f"问题：{query}"}
            ]
            response = self.clients.chat.chat.completions.create(
                model=self.config.get_generation_model,
                messages=messages,
                temperature=0.1,
                max_tokens=1
            )
            result = response.choices[0].message.content.strip().upper() == "Y"
            logger.info(f"审核结果: {'通过' if result else '拒绝'}")
            return result
        except Exception as e:
            logger.error(f"审核查询失败: {str(e)}")
            return True 