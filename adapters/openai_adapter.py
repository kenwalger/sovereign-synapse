import json
import os
import uuid
from datetime import datetime
from slugify import slugify

class OpenAIAdapter:
    """
    Parses OpenAI conversations.json into Sovereign Synapse Markdown turns.
    """
    def __init__(self, output_path="vault/synapses"):
        self.output_path = output_path

    def _generate_slug(self, text, length=40):
        """Creates a human-readable slug from the first few words of a prompt."""
        return slugify(text[:length])

    def parse(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for convo in data:
            title = convo.get('title') or "Untitled Conversation"
            mapping = convo.get('mapping', {})
            
            for node_id, node in mapping.items():
                message = node.get('message')
                if not message:
                    continue
                
                # We find the 'user' message and look for its child 'assistant' response
                if message.get('author', {}).get('role') == 'user':
                    user_text = "".join(message.get('content', {}).get('parts', []))
                    
                    # Find children (replies)
                    for child_id in node.get('children', []):
                        child_node = mapping.get(child_id)
                        child_msg = child_node.get('message')
                        
                        if child_msg and child_msg.get('author', {}).get('role') == 'assistant':
                            assistant_text = "".join(child_msg.get('content', {}).get('parts', []))
                            timestamp = datetime.fromtimestamp(message.get('create_time'))
                            
                            self.write_turn(
                                user_text=user_text,
                                assistant_text=assistant_text,
                                timestamp=timestamp,
                                model=child_msg.get('metadata', {}).get('model_slug', 'gpt-unknown'),
                                original_convo_id=convo.get('id')
                            )

    def write_turn(self, user_text, assistant_text, timestamp, model, original_convo_id):
        # Human-Readable Filename: YYYY-MM-DD-HHMM-[SLUG].md
        slug = self._generate_slug(user_text)
        filename = f"{timestamp.strftime('%Y-%m-%d-%H%M')}-{slug}.md"
        
        os.makedirs(self.output_path, exist_ok=True)
        
        # YAML Frontmatter
        frontmatter = [
            "---",
            f"uuid: urn:uuid:{uuid.uuid4()}",
            f"source: gpt_export",
            f"model: {model}",
            f"original_timestamp: {timestamp.isoformat()}",
            f"original_convo_id: {original_convo_id}",
            "preamble: false", # Default to false, let logic flag it later
            "---"
        ]
        
        content = "\n".join(frontmatter) + f"\n\n### User\n{user_text}\n\n### Assistant\n{assistant_text}"
        
        with open(os.path.join(self.output_path, filename), 'w', encoding='utf-8') as f:
            f.write(content)