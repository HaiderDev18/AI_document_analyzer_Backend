import openai
import logging
import tiktoken
from typing import List, Tuple, Dict, Any
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

    def generate_answer_by_llm(self, similarity_text: str, user_query: str, history: list = None):
        """
        Generate an answer using LLM with context, adapting format based on question type.
        Returns: (answer_text, full_response_object)
        """
        try:
            user_prompt = f"""
                You are an expert AI legal counsel assistant. Your job is to ANSWER THE USER'S ACTUAL QUESTION through both explicit text analysis and intelligent interpretation of implicit meanings.

                **Core Principle:**
                Legal and contractual questions require INTERPRETATION at multiple levels:
                - Explicit: What is directly stated
                - Implicit: What is logically implied or follows from stated terms
                - Structural: What the document's organization and relationships reveal
                - Contextual: What standard practices and legal principles suggest

                **Context:**
                {similarity_text}

                **Question:**
                {user_query}

                **How to Answer:**

                1. **Understand what the user is really asking**
                   - "What documents overrule others?" → They want the precedence hierarchy
                   - "Who is liable for X?" → They want to know responsibility allocation
                   - "When does Y happen?" → They want the trigger/timeline/condition
                   - "Can we do Z?" → They want to know rights and limitations

                2. **Search for answers at multiple levels:**

                   **Level 1 - Explicit Information:**
                   - Direct statements and clearly defined terms
                   - Specific clauses that address the question

                   **Level 2 - Implicit Information:**
                   - Logical implications from stated terms (e.g., if X must happen before Y, then Y cannot happen until X is complete)
                   - Negative space reasoning (e.g., if only Party A can terminate, implicitly Party B cannot)
                   - Definitional implications (e.g., "exclusive rights" implies others are excluded)
                   - Conditional relationships (e.g., if payment triggers obligation, non-payment implies no obligation)
                   - Cross-referencing between clauses that together answer the question

                   **Level 3 - Structural Information:**
                   - Document hierarchy and section relationships
                   - Amendment and override structures
                   - Definitions that cascade through the document
                   - Precedence established by "notwithstanding" or "subject to" clauses

                   **Level 4 - Contextual Information:**
                   - Standard legal interpretation principles (specificity, hierarchy, context)
                   - Industry-standard practices and norms
                   - Typical contractual frameworks
                   - Legal doctrines (e.g., contra proferentem, good faith)

                3. **Interpretation Methodology:**

                   **When information is implicit:**
                   - Identify the relevant clauses that, when read together, answer the question
                   - Explain the logical chain: "Clause A states X, which combined with Clause B stating Y, means Z"
                   - Note: "⚠️ This interpretation is based on [specific clauses/logical implication/document structure]"

                   **Examples of implicit reasoning:**
                   - Q: "Can Party B assign this contract?" 
                     A: "Section 5.3 states 'Party A may assign with written consent.' Since only Party A's assignment rights are mentioned and contracts typically require mutual consent for assignment, Party B likely cannot assign without explicit permission. ⚠️ Based on standard interpretation that enumeration of one party's rights suggests limitation of the other's."

                   - Q: "What happens if payment is 60 days late?"
                     A: "Section 4.2 states late fees apply after 30 days, and Section 4.5 allows termination for 'material breach.' While not explicitly stated, 60-day late payment would likely constitute material breach given the 30-day threshold for lesser penalties. ⚠️ Based on the escalation structure implied by these provisions."

                4. **Structure your response:**

                   **For explicit answers:**
                   - State the answer clearly
                   - Cite specific clause(s)
                   - Provide direct quotations when helpful

                   **For implicit answers:**
                   - State the interpreted answer clearly
                   - Explain the reasoning path step-by-step
                   - Reference the clauses/structure that support the interpretation
                   - Add interpretive disclaimer: "⚠️ This is based on [reasoning type] as it's not explicitly stated"

                   **For questions requiring both:**
                   - Start with explicit information
                   - Layer on implicit interpretations
                   - Clearly distinguish between what's stated vs. implied

                5. **ONLY say "Information not found" if:**
                   - The question asks for a specific fact (date, amount, name, address) that is neither stated nor derivable
                   - No explicit text, implicit meaning, structural relationship, or reasonable interpretation can answer it
                   - The question requires information genuinely outside the document's scope
                   - You cannot make any defensible inference even using standard legal principles

                **Response Format:**

                **Explicit Information Available:**
                "[Direct answer] — Per Section X.Y: '[relevant quote]'"

                **Implicit Information (requires interpretation):**
                "[Interpreted answer] — Based on:
                • Section X.Y states: [clause 1]
                • Section A.B states: [clause 2]
                • Together, these imply: [reasoning]
                ⚠️ This interpretation is based on [logical implication/document structure/standard practice]"

                **Mixed (explicit + implicit):**
                "[Answer] — Section X explicitly states [explicit part]. While [implicit aspect] isn't directly stated, it can be reasonably inferred from [reasoning]. ⚠️ The latter part is interpretive."

                **Types of interpretive reasoning to apply:**
                - **Inclusio unius est exclusio alterius**: Mentioning one thing excludes others
                - **Noscitur a sociis**: Words are known by their companions (context)
                - **Ejusdem generis**: General terms limited by specific preceding terms
                - **Expressio unius est exclusio alterius**: Expressing one excludes others
                - **Logical necessity**: If A requires B, then not-B means not-A
                - **Structural precedence**: Later/specific provisions override earlier/general ones
                - **Cross-referential synthesis**: Combining multiple clauses to derive meaning

                **Remember:** 
                - Users need actionable guidance on what documents MEAN, not just what they SAY
                - Many questions are answerable through interpretation even when not explicitly addressed
                - Be transparent about when you're interpreting vs. citing
                - Use your analytical capabilities fully—you're a legal analyst, not just a search engine
                - Good legal analysis often requires reading between the lines while being clear about doing so
                """

            messages = []
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": user_prompt})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )

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
