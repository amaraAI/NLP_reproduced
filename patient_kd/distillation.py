import torch
import torch.nn as nn
import torch.nn.functional as F
from operator import itemgetter


class PatientDistillation(nn.Module):
    def __init__(self, t_config, s_config):
        super(PatientDistillation, self).__init__()
        self.t_config = t_config
        self.s_config = s_config

    def forward(self, t_model, s_model, order, input_ids, token_type_ids, attention_mask, labels, args):
        with torch.no_grad():
            t_outputs = t_model(input_ids=input_ids,
                                token_type_ids=token_type_ids,
                                attention_mask=attention_mask)

        s_outputs = s_model(input_ids=input_ids,
                            token_type_ids=token_type_ids,
                            attention_mask=attention_mask,
                            labels=labels
                            )

        t_logits, t_features = t_outputs[0], t_outputs[-1]
        train_loss, s_logits, s_features = s_outputs[0], s_outputs[1], s_outputs[-1]
        T = args.temperature
        #print(f"the size of the t_logits is {t_logits.size()}")
        #print(f"the size of the s_logits is {s_logits.size()}")
        #print(f"the size of the s_features is {len(t_features)}")
        soft_targets = F.softmax(t_logits / T, dim=-1)
        log_probs = F.log_softmax(s_logits / T, dim=-1)
        soft_loss = F.kl_div(log_probs, soft_targets.detach(), reduction='batchmean') * T * T

        t_features = torch.cat(t_features[1:-1], dim=0).view(self.t_config.num_hidden_layers - 1,
                                                             -1,
                                                             args.max_seq_length,
                                                             self.t_config.hidden_size)[:, :, 0]

        s_features = torch.cat(s_features[1:-1], dim=0).view(self.s_config.num_hidden_layers - 1,
                                                             -1,
                                                             args.max_seq_length,
                                                             self.s_config.hidden_size)[:, :, 0]

        t_features = itemgetter(order)(t_features)
        t_features = t_features / t_features.norm(dim=-1).unsqueeze(-1)
        s_features = s_features / s_features.norm(dim=-1).unsqueeze(-1)
        distill_loss = F.mse_loss(s_features, t_features.detach(), reduction="mean")
        return train_loss, soft_loss, distill_loss