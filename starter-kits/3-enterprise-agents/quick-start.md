# 🚀 Enterprise Agents Quick Start

[← Back to Enterprise Agents overview](./README.md)

Get started quickly by exploring the following resources that provide step-by-step guidance for building enterprise agents.

## Copilot Dev Camp

The **Copilot Dev Camp** is your one-stop destination for learning how to build agents that extend Microsoft 365 Copilot. Access comprehensive tutorials, hands-on labs, and sample code to accelerate your development journey.

🔗 **Main Portal**: [https://aka.ms/copilotdevcamp](https://aka.ms/copilotdevcamp)

### Building with Copilot Studio

Learn how to create powerful agents using Microsoft Copilot Studio's visual designer and low-code capabilities:

🔗 **Copilot Studio Guide**: [https://microsoft.github.io/copilot-camp/pages/make/copilot-studio/](https://microsoft.github.io/copilot-camp/pages/make/copilot-studio/)

### Extending Microsoft 365 Copilot

Discover how to extend Microsoft 365 Copilot with custom agents, plugins, and connectors:

🔗 **Extend M365 Copilot**: [https://microsoft.github.io/copilot-camp/pages/extend-m365-copilot/](https://microsoft.github.io/copilot-camp/pages/extend-m365-copilot/)

### Building Agents for Microsoft 365 Copilot

Discover how to build Custom Engine Agents for Microsoft 365 Copilot:

🔗 **Build for M365 Copilot**: [https://microsoft.github.io/copilot-camp/pages/custom-engine/](https://microsoft.github.io/copilot-camp/pages/custom-engine/)

## Agent Academy

The **Agent Academy** provides structured learning paths and expert-led training to help you master agent creation with Microsoft Copilot Studio. Whether you're new to building agents or looking to enhance your skills, Agent Academy offers curated content to guide you through the entire development lifecycle in Copilot Studio.

🔗 **Agent Academy**: [https://aka.ms/agentacademy](https://aka.ms/agentacademy)

## Getting Started Checklist

1. ✅ Visit the Copilot Dev Camp portal / Agent Academy and review the available learning paths
2. ✅ Set up your development environment (VS Code + ATK or Copilot Studio)
3. ✅ Explore the sample projects and templates provided in the documentation
4. ✅ Identify your target enterprise scenario and define your agent's capabilities
5. ✅ Start building and iterating on your solution

### Step by Step Starter Kit

Follow these step-by-step guides to get started with each development approach.

#### 🔹 Declarative Agents (DA)

Build Declarative Agents using Microsoft 365 Agents Toolkit in Visual Studio Code:

1. **Install Visual Studio Code**
   - Download and install VS Code from [https://code.visualstudio.com/download](https://code.visualstudio.com/download)

2. **Install Microsoft 365 Agents Toolkit (ATK)**
   - Open VS Code and navigate to the Extensions view (`Ctrl+Shift+X`)
   - Search for "Microsoft 365 Agents Toolkit" and click **Install**
   - Alternatively, install from the marketplace: [https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension)

3. **Install Prerequisites**
   - Install [Node.js](https://nodejs.org/) (LTS version recommended)
   - Ensure you have a Microsoft 365 developer tenant with Copilot enabled
   - Sign in to your Microsoft 365 account in VS Code using ATK

4. **Create a New Declarative Agent**
   - Open the Command Palette (`Ctrl+Shift+P`) and select **M365 Agents Toolkit: Create a New App**
   - Choose **Agent** → **Declarative Agent**
   - Follow the wizard to configure your agent's name, capabilities, and grounding sources
   - ATK will scaffold the project with the declarative manifest and configuration files

5. **Configure and Test**
   - Define your agent's instructions and knowledge sources in the declarative manifest
   - Press `F5` to launch your agent in Microsoft 365 Copilot for testing
   - Iterate on your agent's configuration based on test results

#### 🔹 Custom Engine Agents (CEA)

Build Custom Engine Agents with full code control using Visual Studio and C#:

1. **Install Visual Studio**
   - Download and install Visual Studio 2022 (Community, Professional, or Enterprise) from [https://visualstudio.microsoft.com/downloads/](https://visualstudio.microsoft.com/downloads/)
   - During installation, select the **ASP.NET and web development** workload
   - Also select the **Azure development** workload for cloud deployment capabilities

2. **Install Microsoft 365 Agents Toolkit (ATK)**
   - Open Visual Studio and navigate to **Extensions** → **Manage Extensions**
   - Search for "Microsoft 365 Agents Toolkit" and click **Download**
   - Restart Visual Studio to complete the installation
   - Alternatively, download from the marketplace: [https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.MicrosoftTeamsToolkit2022](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.MicrosoftTeamsToolkit2022)

3. **Install Prerequisites**
   - Install [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) (required for C# agent development)
   - Install [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) for Azure resource provisioning
   - Ensure you have a Microsoft 365 developer tenant and Azure subscription
   - Sign in to your Microsoft 365 and Azure accounts in Visual Studio

4. **Create a New Custom Engine Agent**
   - In Visual Studio, select **File** → **New** → **Project**
   - Search for "Microsoft 365 Agent" or use the ATK project templates
   - Choose **Custom Engine Agent** with **C#** as the language
   - Configure your project name, location, and solution settings
   - Select an AI model provider (Azure OpenAI recommended for enterprise scenarios)
   - ATK will scaffold the C# project with Bot Framework integration and AI orchestration code

5. **Implement Your Agent Logic**
   - Customize the agent's conversation handling in the generated C# code
   - Use dependency injection and strongly-typed models for maintainable code
   - Integrate with external APIs and MCP servers using HttpClient or SDK libraries
   - Implement authentication flows using Microsoft Entra ID and MSAL.NET
   - Add Adaptive Card responses for rich UI experiences using the AdaptiveCards NuGet package

6. **Test and Deploy**
   - Press `F5` to run your agent locally with the Bot Framework Emulator
   - Use Visual Studio's debugging tools to set breakpoints and inspect variables
   - Test in Microsoft 365 Copilot using the sideloading feature
   - Deploy to Azure App Service or Azure Container Apps using Visual Studio's publish feature or ATK's deployment commands

#### 🔹 Microsoft Copilot Studio (MCS)

Build agents using the low-code/no-code Microsoft Copilot Studio platform:

1. **Access Microsoft Copilot Studio**
   - Navigate to [https://copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
   - Sign in with your Microsoft 365 organizational account
   - Ensure you have the appropriate Copilot Studio license

2. **Create a New Agent**
   - Click **Create** on the home page
   - Choose **New agent** to start from scratch or select a template
   - Provide a name and description for your agent
   - Configure the agent's primary language and tone

3. **Configure Knowledge Sources**
   - Add knowledge sources such as SharePoint sites, websites, or uploaded documents
   - Configure the agent to ground responses in your organizational data
   - Set up data source authentication if required

4. **Design Conversation Topics**
   - Create topics to handle specific user intents
   - Use the visual authoring canvas to design conversation flows
   - Add trigger phrases that activate each topic
   - Configure actions, conditions, and variable handling

5. **Extend with Actions and Tools**
   - Add Power Automate flows to integrate with external systems
   - Configure tools to read/write data from MCP servers or APIs
   - Set up authentication for secure connector access

6. **Publish and Deploy**
   - Test your agent using the built-in test chat
   - Publish your agent to make it available in Microsoft 365 Copilot
   - Configure channels (Teams, web, etc.) for deployment
   - Monitor usage and iterate based on analytics