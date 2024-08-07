PYTHON_VERSION := 3.11.2
VENV_NAME := tlgrm_business_voice_converter

.PHONY: setup activate delete clean update

setup:
	pyenv install $(PYTHON_VERSION) -s
	pyenv virtualenv $(PYTHON_VERSION) $(VENV_NAME)
	pyenv local $(VENV_NAME)
	pip install --upgrade pip
	pip install -r requirements.txt

activate:
	@echo "To activate the environment, run:"
	@echo "pyenv activate $(VENV_NAME)"

delete:
	pyenv uninstall -f $(VENV_NAME)

clean: delete
	pyenv local --unset

update:
	pip install --upgrade -r requirements.txt
