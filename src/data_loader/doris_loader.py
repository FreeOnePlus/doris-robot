import os
import logging
from glob import glob
import re
from typing import List
from pathlib import Path
from ..vectorstore.milvus_store import MilvusStore
from settings import config
from ..qa.rag_engine import RAGEngine
import hashlib

logger = logging.getLogger(__name__)

class DorisLoader:
    def __init__(self, docs_path: Path):
        """
        初始化文档加载器
        Args:
            docs_path: doris-website项目的根路径
        """
        self.docs_path = docs_path
        self.versions = ["2.0", "2.1", "3.0"]  # 支持的版本列表
        self.latest_version = "3.0"
        self.rag_engine = RAGEngine()  # 初始化RAG引擎
        logger.info(f"初始化文档加载器，文档路径: {docs_path}")
        
    def _should_hide_version(self, version: str) -> bool:
        """判断是否需要隐藏版本号"""
        return version == "2.1"

    def _parse_version(self, url: str) -> str:
        """从URL解析版本号"""
        # 匹配类似 /docs/3.0/ 或 /version-3.0/ 的路径
        version_pattern = r'/(?:docs/|version-)(\d+\.\d+)/'
        match = re.search(version_pattern, url)
        if match:
            return match.group(1)
        # 默认返回最新版
        return self.latest_version

    def _generate_clean_url(self, url: str, version: str) -> str:
        """生成清理后的URL"""
        if version == "2.1":
            # 移除版本路径
            return re.sub(r'/docs/\d+\.\d+/', '/docs/', url)
        return url

    def load_documents(self):
        """加载所有Doris文档并按段落分割"""
        try:
            text_chunks = []
            
            # 基础路径：i18n/zh-CN/
            base_path = os.path.join(self.docs_path, "i18n", "zh-CN")
            
            if not os.path.exists(base_path):
                raise FileNotFoundError(f"基础文档路径不存在: {base_path}")
            
            logger.info(f"开始加载文档，基础路径: {base_path}")
            
            for version in self.versions:
                logger.info(f"处理版本: {version}")
                
                # 处理社区文档
                community_path = os.path.join(base_path, "docusaurus-plugin-content-docs-community")
                if os.path.exists(community_path):
                    logger.info(f"处理社区文档: {community_path}")
                    chunks = self._process_docs(community_path, version, is_community=True)
                    text_chunks.extend(chunks)
                    logger.info(f"社区文档处理完成，获取 {len(chunks)} 个文档块")
                
                # 处理版本文档
                if version == 'dev':
                    docs_path = os.path.join(base_path, f"docusaurus-plugin-content-docs/current")
                else:
                    docs_path = os.path.join(base_path, f"docusaurus-plugin-content-docs/version-{version}")
                
                if os.path.exists(docs_path):
                    logger.info(f"处理版本文档: {docs_path}")
                    chunks = self._process_docs(docs_path, version)
                    text_chunks.extend(chunks)
                    logger.info(f"版本文档处理完成，获取 {len(chunks)} 个文档块")
                else:
                    logger.warning(f"文档路径不存在: {docs_path}")
            
            if not text_chunks:
                raise ValueError("未能加载到任何文档内容")
            
            logger.info(f"文档加载完成，总共获取 {len(text_chunks)} 个文档块")
            
            # 在加载文档时添加版本验证
            for doc in text_chunks:
                version = self._parse_version(doc['url'])
                if version not in self.versions:
                    logger.warning(f"无效版本: {version} | URL: {doc['url']}")
                doc['version'] = version
            
            return text_chunks
        
        except Exception as e:
            logger.error(f"加载文档失败: {str(e)}")
            raise
    
    def _clean_content(self, content):
        """清理文档内容，去除license头等无关内容"""
        # 移除license头
        license_pattern = r'<!--\s*Licensed to the Apache Software Foundation[\s\S]*?under the License\.\s*-->'
        content = re.sub(license_pattern, '', content, flags=re.MULTILINE)
        
        # 移除其他可能的HTML注释
        content = re.sub(r'<!--[\s\S]*?-->', '', content)
        
        # 移除多余的空行
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        return content.strip()

    def _split_by_headings(self, content, file_path):
        """按Markdown标题层级精确切分文档"""
        try:
            lines = content.split('\n')
            chunks = []
            current_chunk = []
            current_headings = []
            current_level = 0

            for line in lines:
                # 检测标题行
                if line.startswith('#'):
                    # 计算标题层级
                    level = line.count('#', 0, line.find(' '))
                    title = line.strip('#').strip()
                    
                    # 当遇到同级或上级标题时，提交当前块
                    if level <= current_level and current_chunk:
                        chunks.append({
                            "content": '\n'.join(current_chunk),
                            "headings": current_headings.copy(),
                            "level": current_level
                        })
                        current_chunk = []
                    
                    # 更新当前标题路径
                    current_headings = current_headings[:level-1] + [title]
                    current_level = level
                    
                    # 添加标题到新块
                    current_chunk.append(line)
                else:
                    # 非标题行添加到当前块
                    if line.strip():
                        current_chunk.append(line)

            # 添加最后一个块
            if current_chunk:
                chunks.append({
                    "content": '\n'.join(current_chunk),
                    "headings": current_headings,
                    "level": current_level
                })

            # 过滤空内容块
            valid_chunks = [chunk for chunk in chunks if len(chunk["content"].strip()) > 50]
            
            logger.debug(f"文件 {file_path} 切分为 {len(valid_chunks)} 个标题块")
            return valid_chunks

        except Exception as e:
            logger.error(f"标题切分失败: {file_path} - {str(e)}")
            return [{"content": content, "headings": [], "level": 0}]

    def _process_markdown_file(self, file_path, version, is_community=False):
        """处理单个Markdown文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 按标题切分文档
            chunks = self._split_by_headings(content, file_path)
            
            # 生成文档块元数据
            base_url = self._generate_doc_url(file_path, version)
            logger.debug(f"处理文件 {file_path}，版本: {version}，社区文档: {is_community}")
            
            # 新增版本校验
            valid_versions = ['2.0', '2.1', '3.0', 'dev']
            if version not in valid_versions:
                raise ValueError(f"非法版本号: {version}")

            return [{
                "content": chunk["content"],
                "version": version,
                "url": f"{base_url}#{'-'.join(chunk['headings'])}" if chunk["headings"] else base_url,
                "is_community": is_community,
                "headings": chunk["headings"],
                "heading_level": chunk["level"]
            } for chunk in chunks]
            
        except Exception as e:
            logger.error(f"处理文件失败: {file_path} - {str(e)}")
            return []

    def _process_file(self, file_path, version, is_community=False):
        """处理单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 清理内容
            cleaned_content = self._clean_content(content)
            
            # 获取相对路径用于生成URL
            rel_path = os.path.relpath(file_path, self.docs_path)
            
            # 生成URL
            url = self._generate_doc_url(file_path, version)
            
            return {
                "content": cleaned_content,
                "version": version,
                "url": url,
                "is_community": is_community
            }
        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {str(e)}")
            return None
    
    def _process_docs(self, path, version, is_community=False):
        """处理指定路径下的所有markdown文档"""
        chunks = []
        file_count = 0
        
        for file_path in glob(os.path.join(path, "**/*.md"), recursive=True):
            file_count += 1
            try:
                # 新增版本验证
                valid_versions = ['2.0', '2.1', '3.0', 'dev']
                if version not in valid_versions:
                    raise ValueError(f"非法版本号: {version}")
                
                # 处理单个文件并获取所有文档块
                file_chunks = self._process_markdown_file(file_path, version, is_community)
                chunks.extend(file_chunks)
                logger.debug(f"文件 {file_path} 分割为 {len(file_chunks)} 个文档块")
                
            except Exception as e:
                logger.error(f"处理文件 {file_path} 失败: {str(e)}")
        
        logger.info(f"处理完成 {file_count} 个文件，生成 {len(chunks)} 个文档块")
        return chunks

    def _generate_doc_url(self, file_path: str, version: str) -> str:
        """生成文档访问URL"""
        # 将文件系统路径转换为web路径
        rel_path = os.path.relpath(file_path, self.docs_path)
        web_path = f"/{rel_path.replace('.md', '')}"
        
        if self._should_hide_version(version):
            # 移除版本路径段
            web_path = re.sub(r'/\d+\.\d+/', '/', web_path)
            return web_path
        
        # 保持其他版本的路径结构
        return web_path 

    def full_process(self, progress_callback=None):
        """完整的文档处理流程"""
        documents = self.load_documents()
        
        # 创建集合
        milvus = MilvusStore()
        milvus.create_collection(config.doc_collection_name)
        
        # 批量插入
        total = len(documents)
        if progress_callback:
            progress_callback(0, total)
        
        records = []
        for i, doc in enumerate(documents):
            # 验证必要字段
            required_fields = ["content", "version", "url"]
            if not all(field in doc for field in required_fields):
                logger.error(f"文档数据不完整: {doc}")
                continue
            
            doc_id = hashlib.md5(doc["url"].encode()).hexdigest()
            records.append({
                "id": doc_id,
                "text": doc["content"],
                "vector": self.rag_engine.get_embedding(doc["content"]),
                "version": doc["version"],
                "url": doc["url"],
                "is_community": doc.get("is_community", False)
            })
            
            # 每处理50个文档触发一次进度更新
            if progress_callback and (i % 50 == 0 or i == total-1):
                progress_callback(i+1, total)
        
        try:
            logger.info(f"开始插入 {len(records)} 条数据到Milvus")
            inserted_count = milvus.batch_insert("doris_docs", records)
            logger.info(f"数据插入完成，成功插入 {inserted_count} 条")
        except Exception as e:
            logger.error(f"最终数据插入失败: {str(e)}")
            raise
        
        return total 