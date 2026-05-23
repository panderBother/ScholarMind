import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

type ConfirmType = "warning" | "danger" | "info";

type ConfirmOptions = {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  type?: ConfirmType;
  showCancel?: boolean;
};

type ConfirmState = ConfirmOptions & {
  resolve: (value: boolean) => void;
};

type MessageType = "success" | "error" | "info" | "warning";

type ToastItem = {
  id: number;
  type: MessageType;
  text: string;
};

type UiContextValue = {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  message: {
    success: (text: string) => void;
    error: (text: string) => void;
    info: (text: string) => void;
    warning: (text: string) => void;
  };
};

const UiContext = createContext<UiContextValue | null>(null);

const CONFIRM_ICON: Record<ConfirmType, typeof AlertTriangle> = {
  warning: AlertTriangle,
  danger: AlertTriangle,
  info: Info,
};

const CONFIRM_ICON_CLS: Record<ConfirmType, string> = {
  warning: "text-amber-500",
  danger: "text-red-500",
  info: "text-primary",
};

const TOAST_ICON: Record<MessageType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
};

const TOAST_CLS: Record<MessageType, string> = {
  success: "border-emerald-200 bg-white text-emerald-800",
  error: "border-red-200 bg-white text-red-800",
  info: "border-blue-200 bg-white text-blue-800",
  warning: "border-amber-200 bg-white text-amber-800",
};

export function UiProvider({ children }: { children: ReactNode }) {
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastId = useRef(0);

  const pushToast = useCallback((type: MessageType, text: string) => {
    const id = ++toastId.current;
    setToasts((prev) => [...prev, { id, type, text }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  }, []);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setConfirmState({ showCancel: true, type: "warning", ...options, resolve });
    });
  }, []);

  const closeConfirm = useCallback((value: boolean) => {
    setConfirmState((cur) => {
      cur?.resolve(value);
      return null;
    });
  }, []);

  const message = useMemo(
    () => ({
      success: (text: string) => pushToast("success", text),
      error: (text: string) => pushToast("error", text),
      info: (text: string) => pushToast("info", text),
      warning: (text: string) => pushToast("warning", text),
    }),
    [pushToast],
  );

  const ctx = useMemo(() => ({ confirm, message }), [confirm, message]);

  const confirmType = confirmState?.type ?? "warning";
  const ConfirmIcon = CONFIRM_ICON[confirmType];

  return (
    <UiContext.Provider value={ctx}>
      {children}

      {confirmState ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-4"
          onClick={() => closeConfirm(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md overflow-hidden rounded-xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3 px-6 pb-2 pt-6">
              <ConfirmIcon className={`mt-0.5 h-6 w-6 shrink-0 ${CONFIRM_ICON_CLS[confirmType]}`} />
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold text-slate-900">
                  {confirmState.title ?? "提示"}
                </h3>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-600">
                  {confirmState.message}
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4">
              {confirmState.showCancel !== false ? (
                <button
                  type="button"
                  onClick={() => closeConfirm(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  {confirmState.cancelText ?? "取消"}
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => closeConfirm(true)}
                className={
                  confirmType === "danger"
                    ? "rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600"
                    : "rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
                }
              >
                {confirmState.confirmText ?? "确定"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="pointer-events-none fixed left-1/2 top-4 z-[110] flex w-full max-w-md -translate-x-1/2 flex-col gap-2 px-4">
        {toasts.map((t) => {
          const Icon = TOAST_ICON[t.type];
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-center gap-2 rounded-lg border px-4 py-3 text-sm shadow-lg ${TOAST_CLS[t.type]}`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1">{t.text}</span>
              <button
                type="button"
                onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
                className="rounded p-0.5 opacity-60 hover:opacity-100"
                aria-label="关闭"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </UiContext.Provider>
  );
}

export function useUi() {
  const ctx = useContext(UiContext);
  if (!ctx) throw new Error("useUi must be used within UiProvider");
  return ctx;
}
