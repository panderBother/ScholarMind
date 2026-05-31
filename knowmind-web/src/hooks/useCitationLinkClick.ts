import { useCallback, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";

import {
  citationByIndex,
  openRagCitation,
  type InlineCitationSource,
} from "@/utils/openRagCitation";
import { citationIndexFromHash, isCitationHash } from "@/utils/linkifyInlineCitations";

export function useCitationLinkClick(kbId: string | undefined, sources: InlineCitationSource[] | undefined) {
  const nav = useNavigate();

  return useCallback(
    (event: MouseEvent<HTMLElement>) => {
      if (!kbId || !sources?.length) return;
      const anchor = (event.target as HTMLElement).closest("a");
      if (!anchor?.href) return;
      if (!isCitationHash(anchor.href)) return;
      event.preventDefault();
      const index = citationIndexFromHash(anchor.href);
      if (index == null) return;
      const citation = citationByIndex(sources, index);
      if (!citation) return;
      void openRagCitation(kbId, citation, nav);
    },
    [kbId, nav, sources],
  );
}
