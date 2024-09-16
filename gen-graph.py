import json
import sys
from collections import defaultdict


class Graph:
    def __init__(self):
        self.calls = []
        self.namespaces = set()
        self.deployments = defaultdict(lambda: defaultdict(lambda: {"containers": []}))

    def add_call(self, source_namespace, source, target_namespace, target):
        self.calls.append((source_namespace, source, target_namespace, target))
        self.namespaces.add(source_namespace)
        self.namespaces.add(target_namespace)

        # Add client container to source deployment with a unique name
        if source_namespace == target_namespace:
            client_container_name = f"{source}-to-{target}"
        else:
            client_container_name = f"{source}-to-{target}-{target_namespace}"

        self.deployments[source_namespace][source]["containers"].append({
            "name": client_container_name,
            "image": "alpine/curl",
            "command": ["/bin/sh", "-c", "--"],
            "args": [f"while true; do curl -si {target}.{target_namespace}; sleep 2; done"]
        })

        # Add server container to target deployment if not already added
        if not any(container["name"] == "server" for container in
                   self.deployments[target_namespace][target]["containers"]):
            self.deployments[target_namespace][target]["containers"].append({
                "name": "server",
                "image": "node",
                "command": ["/bin/sh", "-c"],
                "args": ["echo \"Hi, you called, may I help you?\" > index.html; npx --yes http-server -p 80"]
            })

    def generate_yaml(self):
        yaml_content = ""

        # Generate namespace YAMLs
        for namespace in self.namespaces:
            yaml_content += f"""apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
---
"""

        # Generate deployment and service YAMLs
        for namespace, deployments in self.deployments.items():
            for deployment, data in deployments.items():
                containers = data["containers"]
                yaml_content += f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {deployment}
  namespace: {namespace}
spec:
  selector:
    matchLabels:
      app: {deployment}
  template:
    metadata:
      labels:
        app: {deployment}
    spec:
      containers:
"""
                for container in containers:
                    yaml_content += f"""        - name: {container["name"]}
          image: {container["image"]}
          command: {container["command"]}
          args: {container["args"]}
"""
                yaml_content += "---\n"

                # Generate service YAML for the server container
                if any(container["name"] == "server" for container in containers):
                    yaml_content += f"""apiVersion: v1
kind: Service
metadata:
  name: {deployment}
  namespace: {namespace}
spec:
  selector:
    app: {deployment}
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
---
"""
        return yaml_content


def process_layout(input_file: str):
    """Process the layout file and generate the corresponding YAML files."""
    # Read the JSON layout file
    with open(input_file, 'r') as file:
        layout = json.load(file)

    graph = Graph()
    for source_namespace, source, target_namespace, target in layout:
        graph.add_call(source_namespace, source, target_namespace, target)

    yaml_content = graph.generate_yaml()
    output_file = input_file.replace('.json', '.yaml')

    with open(output_file, "w") as f:
        f.write(yaml_content)

    print(f"YAML file has been generated at '{output_file}' for the layout '{input_file}'.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gen-graph.py <input_json_file1> <input_json_file2> ...")
        sys.exit(1)

    input_files = sys.argv[1:]
    for input_file in input_files:
        process_layout(input_file)
