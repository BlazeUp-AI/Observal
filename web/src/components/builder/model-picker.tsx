// SPDX-FileCopyrightText: 2026 Aryan Iyappan <aryaniyappan2006@gmail.com>
// SPDX-License-Identifier: AGPL-3.0-only


import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useModels } from "@/hooks/use-api";
import { useIdes } from "@/hooks/use-ides";
import { annotateForDisplay, formatModel } from "@/lib/model-display";
import type { CatalogModel } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ModelPickerProps {
  modelName: string;
  onModelNameChange: (value: string) => void;
  modelsByIde: Record<string, string>;
  onModelsByIdeChange: (value: Record<string, string>) => void;
}

function ModelCombobox({
  id,
  value,
  onChange,
  rows,
  placeholder,
  autoLabel,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  rows: CatalogModel[];
  placeholder: string;
  autoLabel: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  const annotated = useMemo(() => annotateForDisplay(rows), [rows]);
  const filtered = useMemo(() => {
    const q = inputValue.trim().toLowerCase();
    if (!q) return annotated;
    return annotated.filter((m) =>
      [m.model_id, m.display_name, m.provider, m.family]
        .filter(Boolean)
        .some((v) => v.toLowerCase().includes(q)),
    );
  }, [annotated, inputValue]);

  function labelForModel(m: (typeof annotated)[number]) {
    const fm = formatModel({
      display_name: m.display_name,
      model_id: m.model_id,
      release_date: m.release_date,
      disambiguate: true,
    });
    return fm.secondary ? `${fm.primary} (${fm.secondary})` : fm.primary;
  }

  function commit(next: string) {
    setInputValue(next);
    onChange(next);
  }

  function handleBlur() {
    setTimeout(() => {
      if (inputValue !== value) onChange(inputValue);
      setOpen(false);
    }, 150);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className="relative">
          <input
            ref={inputRef}
            id={id}
            type="text"
            placeholder={placeholder}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              if (!open) setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={handleBlur}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commit(inputValue);
                setOpen(false);
              }
              if (e.key === "Escape") setOpen(false);
            }}
            className={cn(
              "flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors",
              "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              "pr-16",
            )}
          />
          <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5">
            {inputValue ? (
              <button
                type="button"
                className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                onClick={() => {
                  commit("");
                  inputRef.current?.focus();
                }}
                tabIndex={-1}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}
            <button
              type="button"
              className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              onClick={() => {
                setOpen((v) => !v);
                inputRef.current?.focus();
              }}
              tabIndex={-1}
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>
        </div>
      </PopoverTrigger>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <Command shouldFilter={false}>
          <CommandList>
            <CommandEmpty>
              {inputValue ? (
                <span className="text-xs text-muted-foreground">
                  Press Enter to use <span className="font-mono font-medium">{inputValue}</span>
                </span>
              ) : (
                <span className="text-xs text-muted-foreground">Type a model ID or choose from the catalog</span>
              )}
            </CommandEmpty>
            <CommandGroup heading="Default">
              <CommandItem
                value="auto"
                onSelect={() => {
                  commit("");
                  setOpen(false);
                }}
                onMouseDown={(e) => e.preventDefault()}
              >
                <Check className={cn("mr-2 h-3.5 w-3.5", value ? "opacity-0" : "opacity-100")} />
                <span>{autoLabel}</span>
              </CommandItem>
            </CommandGroup>
            {filtered.length > 0 ? (
              <CommandGroup heading="Models">
                {filtered.slice(0, 100).map((m) => (
                  <CommandItem
                    key={m.model_id}
                    value={m.model_id}
                    onSelect={() => {
                      commit(m.model_id);
                      setOpen(false);
                    }}
                    onMouseDown={(e) => e.preventDefault()}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-3.5 w-3.5 shrink-0",
                        value === m.model_id ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm">
                        {labelForModel(m)}{m.deprecated ? " · deprecated" : ""}
                      </div>
                      <div className="truncate font-mono text-xs text-muted-foreground">
                        {m.model_id}
                      </div>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function ModelPicker({
  modelName,
  onModelNameChange,
  modelsByIde,
  onModelsByIdeChange,
}: ModelPickerProps) {
  const inputId = useId();
  const { data: catalog, isLoading } = useModels();
  const { data: ides, defaultIde } = useIdes();
  const models = useMemo(() => catalog?.models ?? [], [catalog]);
  const idesWithChoice = useMemo(
    () => (ides ?? []).filter((ide) => ide.accepts_model_choice),
    [ides],
  );
  const [selectedIde, setSelectedIde] = useState("");

  useEffect(() => {
    if (idesWithChoice.length === 0) return;
    const fallback = defaultIde && idesWithChoice.some((ide) => ide.name === defaultIde)
      ? defaultIde
      : idesWithChoice[0].name;
    if (!selectedIde || !idesWithChoice.some((ide) => ide.name === selectedIde)) {
      setSelectedIde(fallback);
    }
  }, [defaultIde, idesWithChoice, selectedIde]);

  const selectedIdeMeta = idesWithChoice.find((ide) => ide.name === selectedIde);
  const overrideRows = useMemo(() => {
    if (!selectedIde) return models;
    const supported = models.filter((m) => (m.supported_ides ?? []).includes(selectedIde));
    return supported.length > 0 ? supported : models;
  }, [models, selectedIde]);

  function setOverride(ide: string, value: string) {
    const next = { ...modelsByIde };
    if (value) next[ide] = value;
    else delete next[ide];
    onModelsByIdeChange(next);
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor={inputId} className="text-sm font-medium">
          Default model
        </Label>
        <ModelCombobox
          id={inputId}
          value={modelName}
          onChange={onModelNameChange}
          rows={models}
          placeholder={isLoading ? "Loading models…" : "auto (let the IDE pick)"}
          autoLabel="auto (let the IDE pick)"
        />
        <p className="text-xs text-muted-foreground">
          Pick from the models.dev catalog or type any model ID. Leave blank to let
          the IDE choose.
        </p>
      </div>

      {idesWithChoice.length > 0 ? (
        <div className="space-y-3 rounded-md border border-border bg-muted/20 p-3">
          <div className="space-y-1">
            <Label className="text-sm font-medium">Per harness override</Label>
            <p className="text-xs text-muted-foreground">
              Choose a harness from the allowed IDE list and set a model just for that harness.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-[minmax(160px,220px)_1fr]">
            <Select value={selectedIde} onValueChange={setSelectedIde}>
              <SelectTrigger className="h-10">
                <SelectValue placeholder="Select harness" />
              </SelectTrigger>
              <SelectContent>
                {idesWithChoice.map((ide) => (
                  <SelectItem key={ide.name} value={ide.name}>
                    {ide.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <ModelCombobox
              value={modelsByIde[selectedIde] ?? ""}
              onChange={(value) => setOverride(selectedIde, value)}
              rows={overrideRows}
              placeholder={selectedIdeMeta ? `Use default for ${selectedIdeMeta.display_name}` : "Use default"}
              autoLabel="Use default model"
            />
          </div>
          {Object.keys(modelsByIde).length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(modelsByIde).map(([ide, model]) => {
                const label = ides?.find((item) => item.name === ide)?.display_name ?? ide;
                return (
                  <span key={ide} className="rounded bg-primary/10 px-2 py-1 text-xs text-primary">
                    {label}: <span className="font-mono">{model}</span>
                  </span>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      {catalog?.degraded ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Catalog is using the offline snapshot. Typed model IDs still save.
        </p>
      ) : null}
    </div>
  );
}
