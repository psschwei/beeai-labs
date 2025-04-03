import io, os, sys, yaml, asyncio, subprocess, psutil, traceback, threading, time

import streamlit as st
import streamlit_mermaid as stmd

from src.workflow import Workflow
from cli.common import Console, parse_yaml, read_file

sys_stdout = sys.stdout

global workflow_instance

class StreamlitWorkflowUI:
    def __init__(self, agents_file, workflow_file, prompt='', title='Maestro workflow'):
        self.title = title
        self.prompt = prompt
        self.initial_prompt = 'Enter your prompt here'
        self.agents_file = agents_file
        self.workflow_file = workflow_file

        self.agents_yaml = self.__read_or_parse_yaml(agents_file)
        self.workflow_yaml = self.__read_or_parse_yaml(workflow_file)

        self.workflow = self.__create_workflow(self.agents_yaml, self.workflow_yaml)

    def setup_ui(self):        
        self.__initialize_session_state()
        self.__add_workflow_name_and_files()
        self.__create_workflow_ui()
        self.__create_chat_messages()
        self.__add_use_prompt_and_chat_reset_button()

    # private

    def __read_or_parse_yaml(self, file_or_yaml):
        if os.path.isfile(file_or_yaml):
            return parse_yaml(file_or_yaml)
        else:
            return list(yaml.safe_load_all(file_or_yaml))

    def __read_file_content(self, file_or_string):
        if os.path.isfile(file_or_string):
            return read_file(file_or_string)
        
        return file_or_string

    def __add_workflow_name_and_files(self):
        # add line of workflow: title, agents.yaml, and workflow.yaml
        st.markdown(f"### {self.workflow_yaml[0]['metadata']['name']}")
        cols = st.columns(4)
        with cols[0]:
            with st.popover("agents.yaml"):
                st.markdown("## Formatted agents YAML")
                st.code(self.__read_file_content(self.agents_file), language="yaml", line_numbers=True, wrap_lines=False, height=700)
        with cols[1]:
            with st.popover("workflow.yaml"):
                st.markdown("## Formatted workflow YAML")
                st.code(self.__read_file_content(self.workflow_file), language="yaml", line_numbers=True, wrap_lines=False, height=700)

    def __initialize_session_state(self):
        # Initialize session state for chat history
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {
                    "role": "assistant", 
                    "content": "Welcome to Maestro workflow"
                }]

    def __add_use_prompt_and_chat_reset_button(self):
        with st.form(f"prompt_form:{self.title}"):
            init_prompt = st.selectbox(
                'You might want to try these prompts...',
                [self.prompt,
                 'Enter your prompt here'])

            instructions = 'Enter your prompt here'
            self.prompt = st.text_area(instructions, value=init_prompt, key=f"text_area:{self.title}")

            submitted = st.form_submit_button("Submit")
            if submitted:
                self.__process_chat_input()

    def __process_chat_input(self):
        if self.prompt:
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": self.prompt})
            
            # Display user message
            with st.chat_message("user", avatar="👤"):
                st.markdown(self.prompt)
            
            # Display assistant response
            with st.chat_message("assistant", avatar="🤖"):
                message_placeholder = st.empty()
                message_placeholder.markdown("Thinking...")

                # start and run workflow
                thread = threading.Thread(target=StreamlitWorkflowUI.__start_workflow, args=(self.prompt,))
                thread.start()

                # stream response
                while True:
                    message = ""
                    lines = StreamlitWorkflowUI.__generate_output().splitlines()
                    for line in lines:
                        message = message + f"{line}\n\n"
                    message_placeholder.markdown(message)
                    time.sleep(1)
                    if not thread.is_alive():
                        message = ""
                        lines = StreamlitWorkflowUI.__generate_output().splitlines()
                        for line in lines:
                            message = message + f"{line}\n\n"
                        message_placeholder.markdown(message)
                        break


            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": message})

    def __create_chat_messages(self):
        # Display chat messages
        for message in st.session_state.messages:
            if message["role"] == "assistant":
                with st.chat_message(message["role"], avatar="🤖"):
                    st.markdown(message["content"])
            else:
                with st.chat_message(message["role"], avatar="👤"):
                    st.markdown(message["content"])

    def __create_workflow_ui(self):
        # create workflow
        global workflow_instance
        try:
            workflow_instance = self.__create_workflow(self.agents_yaml, self.workflow_yaml[0])
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Unable to create agents: {str(e)}") from e
        
        # add workflow mermaid diagram to page
        st.markdown("")
        st.markdown(f"###### _Sequence diagram of workflow_")
        mermaid_diagram = workflow_instance.to_mermaid()
        stmd.st_mermaid(mermaid_diagram, key=f"mermaid_diagram:{self.title}")

    def __generate_output():
        global output
        message = output.getvalue()
        return(message)

    def __start_workflow(prompt):
        global output
        output = io.StringIO()
        sys.stdout = output
        asyncio.run(workflow_instance.run(prompt))

    def __create_workflow(self, agents_yaml, workflow_yaml):
        return Workflow(agents_yaml, workflow_yaml)

