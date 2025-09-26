import openai
import logging
import tiktoken
from typing import List, Optional, Tuple, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    Service class for OpenAI API interactions
    """

    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_embedding(self, text: str) -> Tuple[List[float], Any]:
        """
        Generate embedding for text using OpenAI
        Returns: (embedding_vector, full_response_object)
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model, input=text
            )
            embedding = response.data[0].embedding
            return embedding, response
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise Exception(f"Failed to generate embedding: {str(e)}")

    def generate_embeddings_batch(
        self, texts: List[str]
    ) -> Tuple[List[List[float]], Any]:
        """
        Generate embeddings for multiple texts
        Returns: (embedding_vectors, full_response_object)
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model, input=texts
            )
            embeddings = [data.embedding for data in response.data]
            return embeddings, response
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise Exception(f"Failed to generate batch embeddings: {str(e)}")

    def generate_summary(self, text: str) -> Tuple[str, Any]:
        """
        Generate summary of text using OpenAI
        Returns: (summary_text, full_response_object)
        """
        try:
            # System prompt to instruct the model on how to generate Markdown summaries
            system_prompt = """
                You are a professional document summarizer. Your job is to read the user-provided document and produce a concise Markdown summary.

                Core rules:
                - Keep the summary **very short**: one or two paragraphs maximum.
                - Write in clear, simple, confident, and professional language.
                - Do NOT include tables, headings, or long detail.
                - Do NOT add, infer, or hallucinate anything not present in the document.
                - The summary should be enough for a new reader to immediately understand what the document is about without reading the full content.

                Markdown formatting requirements:
                - Output plain paragraphs only (no headings, no tables).
                - Use **bold** sparingly for emphasis on important terms, if necessary.
                - The text must be valid Markdown but remain minimal and clean.

                Output constraints:
                - Return **only** the Markdown summary (no extra explanations, no commentary).
            """

            # User prompt with explicit Markdown output requirements
            user_prompt = f"""
                # User Prompt

                You will receive the full content of a document below. Please:
                - Read and understand the content thoroughly.
                - Identify the main idea, purpose, and key points.
                - Create an accurate, **short** summary (1–2 paragraphs maximum).
                - Do not use headings, subheadings, or tables.
                - Keep the summary simple, clear, and professional.
                - Do not hallucinate or add information not in the document.
                - Return only the Markdown summary.

                # Document Content
                {text}

                # Generate the summary now (1–2 paragraphs, Markdown only)
            """

            # Requesting the completion from the model
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "developer", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            # Extracting the summary from the model's response
            summary = response.choices[0].message.content.strip()
            return summary, response

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise Exception(f"Failed to generate summary: {str(e)}")

    def generate_answer_by_llm(self, similarity_text: str, user_query: str):
        """
        Generate an answer using LLM with context, prioritizing yes/no answers only when appropriate,
        and providing detailed summaries when needed.
        Returns: (answer_text, full_response_object)
        """
        try:
            # system_prompt = """

            # """

            user_prompt = f"""
            You are a helpful assistant. Answer the user's question based on the provided context.
            For yes/no questions, give a clear 'Yes' or 'No' with a brief explanation.
            For non-yes/no questions, provide a concise summary of the main points.

            Context: {similarity_text}
            Question: {user_query}

            Instructions:
            - For yes/no questions, answer with 'Yes' or 'No' and a brief explanation.
            - For summary questions, provide a concise summary of the key points.
            - If there's insufficient information, state that the answer can't be provided.
            - Focus on relevance and clarity.

            Example 1 (Yes/No Question):
            - **Question**: "Is this contract valid?"
            - **Answer**: "Yes."

            Example 2 (Summary Question):
            - **Question**: "What is this document about?"
            - **Answer**: "A subcontract agreement detailing work scope, payment schedule, milestones, and responsibilities."
            """

            # Send the request to the LLM client
            response = self.client.chat.completions.create(
                model="o3",
                messages=[
                    # {"role": "developer", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                # max_tokens=self.max_tokens
                # temperature=0.7
            )

            # Extract the generated answer
            answer = response.choices[0].message.content.strip()
            return answer, response

        except Exception as e:
            logger.error(f"Error generating LLM answer: {str(e)}")
            raise Exception(f"Failed to generate LLM answer: {str(e)}")

    def generate_risk_factors(self, text: str):
        """
        Generate answer using LLM with context
        Returns: (answer_text, full_response_object)
        """
        try:
            system_prompt = """
                #System Prompt

                You are a professional risk auditor specialized in reviewing documents for sensitive or confidential content. Your role is to scan the provided document carefully and extract any information that poses a **risk**, such as personal data, financial information, or confidential business details.

                Your responsibilities:

                * Identify actual risk factors **present in the document**. Do **not** invent or assume anything that is not explicitly stated.
                * For each risk, return a JSON object with:

                * `risk_factor`: The category of risk (e.g., Personal Information, Financial Information).
                * `description`: A short explanation of why this is risky or sensitive.
                * `reference`: The exact phrase or sentence from the document where this risk appears.

                Strict Output Rules:

                * Return a single, valid **JSON object** with a key `"risk_factors"` that holds an array of all detected risk items.
                * **No explanations, comments, headings, or non-JSON output. Only return the JSON.**
                * If no risk factors are found, return:
                {
                    "risk_factors": []
                }

                Style and Conduct:

                * **Professional, accurate, and non-speculative.**
                * **Never hallucinate** — only analyze and report what is **directly stated** in the document.
                * Ensure output is **clean, well-formatted**, and suitable for integration into automated systems.
                """

            user_prompt = f"""
                #User Prompt

                I’m going to provide you with a piece of text or a document. I want you to:

                1. Carefully read the content and identify any **potential risk factors** — anything sensitive, confidential, or inappropriate to share (e.g., personal data, financial info, contact details, internal company matters).
                2. For each issue, provide:

                * The category of risk (`risk_factor`)
                * A brief reason why it’s considered risky (`description`)
                * The **exact reference** or quote from the document where this occurs (`reference`)

                **Output Format:**

                Return a valid JSON object, using this structure:

                {{
                "risk_factors": [
                    {{
                    "risk_factor": "Type of Risk",
                    "description": "Why it's risky.",
                    "reference": "Exact example from the text."
                    }}
                ]
                }}

                3. If there are **no risks**, return:

                {{
                "risk_factors": []
                }}

                **Important Instructions:**

                * **Do NOT hallucinate**. Only report risks that are actually present in the text.
                * **Do NOT summarize or explain anything outside the JSON.**
                * Keep the tone **professional and accurate**.
                * The output must be **only the JSON**, no extra text before or after.

                #Document Content
                {text}

                # Generate Risk Factors in JSON format
                """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "developer", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            risk_factors = response.choices[0].message.content.strip()
            print("risk_factors", risk_factors)
            return risk_factors, response
        except Exception as e:
            # logger.error(f"Error generating risk factors: {str(e)}")
            raise Exception(f"Failed to generate risk factors: {str(e)}")

    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """
        Count tokens in text for the embedding model
        """
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {str(e)}")
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4

    def chat_completion(self, messages: List[Dict[str, str]]) -> Tuple[str, Any]:
        """
        Generate chat completion with optional context
        Returns: (response_text, full_response_object)
        """
        try:
            system_message = "You are a helpful assistant that answers questions based on provided documents."

            chat_messages = [{"role": "system", "content": system_message}] + messages

            response = self.client.chat.completions.create(
                model=self.model,
                messages=chat_messages,
            )

            content = response.choices[0].message.content.strip()
            return content, response
        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            raise Exception(f"Failed to generate chat completion: {str(e)}")
