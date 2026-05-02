import { defineStore } from "pinia";
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

export interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  nodes: unknown[];
  edges: unknown[];
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export const useTemplateStore = defineStore("templates", () => {
  const templates = ref<Template[]>([]);
  const loading = ref(false);

  async function loadTemplates() {
    loading.value = true;
    try {
      templates.value = await invoke<Template[]>("template_list");
    } finally {
      loading.value = false;
    }
  }

  async function createTemplate(
    name: string,
    description: string,
    category: string,
    nodes: unknown[],
    edges: unknown[],
    tags: string[] = [],
  ): Promise<Template> {
    const t = await invoke<Template>("template_create", {
      name,
      description,
      category,
      nodes,
      edges,
      tags,
    });
    templates.value.unshift(t);
    return t;
  }

  async function deleteTemplate(id: string) {
    await invoke("template_delete", { id });
    templates.value = templates.value.filter((t) => t.id !== id);
  }

  async function saveFromWorkflow(
    name: string,
    description: string,
    category: string,
    nodes: unknown[],
    edges: unknown[],
  ): Promise<Template> {
    const t = await invoke<Template>("template_save_from_workflow", {
      name,
      description,
      category,
      nodes,
      edges,
    });
    templates.value.unshift(t);
    return t;
  }

  return {
    templates,
    loading,
    loadTemplates,
    createTemplate,
    deleteTemplate,
    saveFromWorkflow,
  };
});
