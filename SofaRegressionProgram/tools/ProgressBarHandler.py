
class ProgressBarHandler:
    def __init__(self, total, disable = False):
        self.enable_progress_bar = not disable
        self.description = ""

        if self.enable_progress_bar:
            try:
                from tqdm import tqdm
                self.tqdm_object = tqdm(total=total)
            except ModuleNotFoundError:
                print('warning: tqdm is needed if you want to enable progress bars.')
                self.enable_progress_bar = False
                self.tqdm_object = None

    def set_description(self, description):
        if self.enable_progress_bar:
            self.tqdm_object.set_description(description)

    def update(self, nb_step):
        if self.enable_progress_bar:
            self.tqdm_object.update(nb_step)

    def close(self):
        if self.enable_progress_bar:
            self.tqdm_object.close()
