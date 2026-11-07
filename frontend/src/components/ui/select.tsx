"use client";

import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

export type SelectOption = { value: string; label: string; disabled?: boolean };

type Position = { top?: number; bottom?: number; left: number; width: number; maxHeight: number };

export function Select({ value, options, onChange, ariaLabel, className = "", disabled = false, id }: {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  ariaLabel?: string;
  className?: string;
  disabled?: boolean;
  id?: string;
}) {
  const listId = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [position, setPosition] = useState<Position>();
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);
  const selectedIndex = Math.max(0, options.findIndex(option => option.value === value));
  const selected = options[selectedIndex];

  const place = useCallback(() => {
    const button = trigger.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom - 12;
    const above = rect.top - 12;
    const dropUp = below < 200 && above > below;
    setPosition({
      ...(dropUp ? { bottom: window.innerHeight - rect.top + 6 } : { top: rect.bottom + 6 }),
      left: rect.left,
      width: Math.max(rect.width, 160),
      maxHeight: Math.min(300, Math.max(120, dropUp ? above : below)),
    });
  }, []);

  const close = useCallback((focus = false) => {
    setOpen(false);
    if (focus) trigger.current?.focus();
  }, []);

  const openMenu = useCallback(() => {
    if (disabled) return;
    // Modal dialogs make everything outside them inert, including body portals.
    setPortalTarget(trigger.current?.closest("dialog") ?? document.body);
    place();
    setActive(selectedIndex);
    setOpen(true);
  }, [disabled, place, selectedIndex]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (menu.current?.contains(event.target as Node) || trigger.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    const update = () => place();
    const onDialogClose = () => setOpen(false);
    portalTarget?.addEventListener("close", onDialogClose);
    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      portalTarget?.removeEventListener("close", onDialogClose);
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, place, portalTarget]);

  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  function move(direction: 1 | -1) {
    if (!options.length) return;
    let index = active;
    for (let step = 0; step < options.length; step += 1) {
      index = (index + direction + options.length) % options.length;
      if (!options[index]?.disabled) break;
    }
    setActive(index);
  }

  function choose(index: number) {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    close(true);
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!open) {
      if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        openMenu();
      }
      return;
    }
    switch (event.key) {
      case "ArrowDown": event.preventDefault(); move(1); break;
      case "ArrowUp": event.preventDefault(); move(-1); break;
      case "Home": event.preventDefault(); setActive(0); break;
      case "End": event.preventDefault(); setActive(options.length - 1); break;
      case "Enter":
      case " ": event.preventDefault(); choose(active); break;
      case "Escape": event.preventDefault(); close(true); break;
      case "Tab": setOpen(false); break;
    }
  }

  return <>
    <button
      ref={trigger}
      type="button"
      id={id}
      className={`ui-select ${className}`.trim()}
      disabled={disabled}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={open ? listId : undefined}
      aria-label={ariaLabel}
      onClick={() => (open ? close(true) : openMenu())}
      onKeyDown={onKeyDown}
    >
      <span className="ui-select-value">{selected?.label ?? ""}</span>
      <svg className="ui-select-chevron" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </button>
    {open && position && portalTarget && createPortal(
      <div ref={menu} id={listId} className="ui-select-menu" role="listbox" aria-label={ariaLabel} style={position}>
        {options.map((option, index) => <div
          key={`${option.value}:${index}`}
          data-index={index}
          role="option"
          aria-selected={option.value === value}
          aria-disabled={option.disabled || undefined}
          className={`ui-select-option${option.value === value ? " is-selected" : ""}${index === active ? " is-active" : ""}${option.disabled ? " is-disabled" : ""}`}
          onPointerEnter={() => setActive(index)}
          onClick={event => { event.preventDefault(); choose(index); }}
        >
          <span>{option.label}</span>
          {option.value === value && <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6.5 4.5 9 10 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>}
        </div>)}
      </div>,
      portalTarget,
    )}
  </>;
}
