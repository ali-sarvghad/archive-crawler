// Curated quick-pick venues. Names are resolved to OpenAlex source ids at
// query time (so we never depend on hard-coded ids that could drift).
export const CURATED_VENUES = [
  { label: "ACM CHI", query: "Proceedings of the CHI Conference on Human Factors in Computing Systems" },
  { label: "ACM UIST", query: "User Interface Software and Technology" },
  { label: "ACM CSCW", query: "Proceedings of the ACM on Human-Computer Interaction" },
  { label: "ACM DIS", query: "Designing Interactive Systems" },
  { label: "IEEE VIS", query: "IEEE Transactions on Visualization and Computer Graphics" },
  { label: "CHI EA", query: "Extended Abstracts of the CHI Conference" },
  { label: "NeurIPS", query: "Neural Information Processing Systems" },
  { label: "ICML", query: "International Conference on Machine Learning" },
  { label: "ACL", query: "Annual Meeting of the Association for Computational Linguistics" },
  { label: "CVPR", query: "Computer Vision and Pattern Recognition" },
];
