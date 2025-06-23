from langchain.llms import OpenAI
from langchain_deepseek import ChatDeepSeek
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from vectorStore import DrivingMemory

class LLM_Agent:
    def __init__(self, llm_type: str, api_key: str, ):
        # load LLM model
        if llm_type == "":
            print("use gpt model")
            self.llm = OpenAI(
                model="gpt-4.0",
                openai_api_key=api_key,
                temperature=0,
            )
            # TODO
            self.memory = DrivingMemory(emb_type='openai', rule_path=None, emergency_path=None)
        elif llm_type == "deepseek":
            self.llm = ChatDeepSeek(
                model="deepseek-chat",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=api_key,
            )
            # TODO
            self.memory = DrivingMemory(emb_type='hugginface', rule_path=None, emergency_path=None)
        else:
            self.llm = ChatDeepSeek(
                model="deepseek-chat",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=api_key,
            )
            # TODO
            self.memory = DrivingMemory(emb_type='', rule_path=None, emergency_path=None)

        # design output parser
        response_schemas = [
            ResponseSchema(name="analysis", description="analyze the driving situation."),
            ResponseSchema(name="waypoints", description="the predicted waypoints "),
            ResponseSchema(name="end_prob", description="a float number whether the driving stop.")

        ]
        self.output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
        self.format_instructions = self.output_parser.get_format_instructions()

        self.message = []

        # design prompt
        system_template = "You are a driver assistant for autonomous driving. " \
                          "The surroundings of the ego vehicle and some driving information are provided as follows."
        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
        self.message.append(system_message_prompt)

        human_template = "{scenario_description}"\
                         "The current instruction you receive is {instruction}. "\
                         "The things you should notice is {notice}. "\
                         "Your current speed is {velocity}, and target point is {target_point}."\
                         "Please analyze the information and generate {waypoint_number} waypoints."\
                         "Then give a float number to show stop probability whether the vehicle should stop. " \
                         "{format_instructions}"
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
        self.message.append(human_message_prompt)

    def run(self, waypoint_number, image_description_front, image_description_left,
            image_description_right, image_description_rear, instruction, notice,
            velocity, target_point):
        scenario_description = f"The front camera shows {image_description_front}, " \
                               f"and the left camera shows {image_description_left}. " \
                               f"The right camera shows {image_description_right}, " \
                               f"and the rear camera shows {image_description_rear}."
        # retrieve
        retrieved_template = "When the similar situations occur, the follow waypoints and actions are suggested."
        examples = self.memory.retriveMemory(scenario_description, top_k=5)
        for example in examples:
            retrieved_template = retrieved_template + "Waypoints:" + example["waypoints"] + \
                                 "; Actions:" + example["action"] + ". "
        retrieved_message_prompt = HumanMessagePromptTemplate.from_template(retrieved_template)
        self.message.append(retrieved_message_prompt)

        # generate prompt
        self.chat_prompt = ChatPromptTemplate.from_messages(self.message)
        messages = self.chat_prompt.format_messages(waypoint_number=waypoint_number,
                                                    scenario_description=scenario_description,
                                                    instruction=instruction,
                                                    notice=notice,
                                                    velocity=velocity,
                                                    target_point=target_point,
                                                    format_instructions=self.format_instructions)
        # llm response
        response = self.llm.invoke(messages)
        print(response.content)
        output_dict = self.output_parser.parse(response.content)  # get dictionary

        # add memory TODO
        self.memory.addMemory(sce_descrip=scenario_description,
                              analysis=output_dict['analysis'],
                              action=output_dict['action'],
                              waypoints=output_dict['waypoints'],)
        return output_dict

