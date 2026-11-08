"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check, Lock } from "lucide-react";

export interface DropdownOption {
  value: string;
  label: string;
  locked?: boolean;
  disabled?: boolean;
  lockReason?: string;
  isDone?: boolean;
}

interface CustomDropdownProps {
  value: string;
  onChange: (value: string) => void;
  options: (string | DropdownOption)[];
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  onBlockedSelect?: (option: DropdownOption) => void;
}

export function CustomDropdown({
  value,
  onChange,
  options,
  placeholder = "Select an option...",
  className = "",
  disabled = false,
  onBlockedSelect,
}: CustomDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  const normalizedOptions: DropdownOption[] = options.map((opt) =>
    typeof opt === "string" ? { value: opt, label: opt } : opt
  );

  const selectedOption = normalizedOptions.find((opt) => opt.value === value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={dropdownRef} className={`relative w-full ${className}`}>
      {/* Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full flex items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl border text-xs text-left transition-all ${
          isOpen
            ? "border-orange-500 bg-zinc-900 text-zinc-100 ring-2 ring-orange-500/20 shadow-md shadow-orange-500/5"
            : "border-zinc-800 bg-zinc-900 hover:border-zinc-700 hover:bg-zinc-900/80 text-zinc-200"
        } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      >
        <span className="truncate flex items-center gap-1.5">
          {selectedOption ? (
            <>
              {selectedOption.locked && <Lock className="h-3 w-3 text-amber-500 shrink-0" />}
              {selectedOption.isDone && <Check className="h-3 w-3 text-emerald-400 shrink-0" />}
              <span className="truncate">{selectedOption.label}</span>
            </>
          ) : (
            <span className="text-zinc-500">{placeholder}</span>
          )}
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-200 ${
            isOpen ? "rotate-180 text-orange-400" : ""
          }`}
        />
      </button>

      {/* Popover Menu */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1.5 z-50 max-h-64 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900/98 backdrop-blur-md p-1.5 shadow-2xl shadow-black/80 ring-1 ring-zinc-700/50 space-y-0.5">
          {normalizedOptions.map((opt) => {
            const isSelected = opt.value === value;
            const isLocked = Boolean(opt.locked || opt.disabled);

            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  if (isLocked) {
                    if (onBlockedSelect) onBlockedSelect(opt);
                    return;
                  }
                  onChange(opt.value);
                  setIsOpen(false);
                }}
                disabled={isLocked}
                title={opt.lockReason || (isLocked ? "Complete prerequisite chapter first" : undefined)}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-xs transition-colors text-left ${
                  isLocked
                    ? "opacity-45 text-zinc-500 cursor-not-allowed hover:bg-zinc-950/60"
                    : isSelected
                    ? "bg-orange-950/40 text-orange-400 font-semibold border-l-2 border-orange-500"
                    : "text-zinc-300 hover:bg-zinc-800/80 hover:text-zinc-100 cursor-pointer"
                }`}
              >
                <div className="flex items-center gap-1.5 min-w-0 flex-1">
                  {isLocked ? (
                    <Lock className="h-3 w-3 text-zinc-500 shrink-0" />
                  ) : opt.isDone ? (
                    <Check className="h-3 w-3 text-emerald-400 shrink-0" />
                  ) : null}
                  <span className="truncate">{opt.label}</span>
                </div>

                {isLocked ? (
                  <span className="shrink-0 text-[10px] text-zinc-500 bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800 font-mono">
                    Locked
                  </span>
                ) : isSelected ? (
                  <Check className="h-3.5 w-3.5 text-orange-400 shrink-0 ml-1" />
                ) : null}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
